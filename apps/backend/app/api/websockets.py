"""
WebSocket endpoint για real-time status updates των Environments.

Αρχιτεκτονική:
  - Ο Celery worker (μετά το GitOps commit) κάνει PUBLISH στο Redis channel: "env:{env_id}:status"
  - Αυτός ο endpoint κάνει SUBSCRIBE στο ίδιο channel
  - Κάθε update προωθείται live στο React frontend

Γιατί Redis Pub/Sub και όχι in-memory Dict:
  - In-memory connections δουλεύουν μόνο με 1 Uvicorn worker process
  - Με Redis, ο Celery worker (που τρέχει σε ξεχωριστό process/pod) μπορεί
    να στέλνει updates σε όλα τα WebSocket connections ανεξάρτητα από το worker
"""
import asyncio
import json
import logging
from typing import Dict, List

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])


class ConnectionManager:
    """
    Διαχειρίζεται τα ενεργά WebSocket connections ανά environment.

    Το in-memory dict κρατάει τα connections του ΤΡΕΧΟΝΤΟΣ process.
    Το Redis Pub/Sub επιτρέπει σε άλλα processes (Celery) να στέλνουν updates.
    """

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, env_id: str) -> None:
        await websocket.accept()
        if env_id not in self.active_connections:
            self.active_connections[env_id] = []
        self.active_connections[env_id].append(websocket)
        logger.info("WebSocket connected for env_id=%s (total: %d)", env_id, len(self.active_connections[env_id]))

    def disconnect(self, websocket: WebSocket, env_id: str) -> None:
        if env_id in self.active_connections:
            self.active_connections[env_id].remove(websocket)
            if not self.active_connections[env_id]:
                del self.active_connections[env_id]
        logger.info("WebSocket disconnected for env_id=%s", env_id)

    async def send_to_env(self, env_id: str, data: dict) -> None:
        """Στέλνει JSON message σε όλα τα connections ενός environment."""
        if env_id not in self.active_connections:
            return
        dead_connections = []
        for ws in self.active_connections[env_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead_connections.append(ws)
        for ws in dead_connections:
            self.active_connections[env_id].remove(ws)


manager = ConnectionManager()


async def redis_listener(env_id: str, websocket: WebSocket) -> None:
    """
    Subscribes στο Redis channel για ένα environment και forward-αρει
    τα messages στο WebSocket.

    Channel format: "env:{env_id}:status"
    Message format: {"status": "Ready", "message": "Environment is ready", "step": "4/4"}
    """
    channel_name = f"env:{env_id}:status"
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(channel_name)
            logger.info("Subscribed to Redis channel: %s", channel_name)

            async for message in pubsub.listen():
                # Αγνοούμε το subscription confirmation message
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                    # Αν το status είναι τελικό (Ready ή Failed), κλείνουμε το channel
                    if data.get("status") in ("Ready", "Failed"):
                        logger.info("Terminal status received for env_id=%s, closing listener", env_id)
                        break
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning("Error forwarding Redis message to WebSocket: %s", e)
    finally:
        await redis_client.aclose()


@router.websocket("/environments/{env_id}")
async def websocket_environment_status(websocket: WebSocket, env_id: str):
    """
    WebSocket endpoint για real-time status updates.

    Ο client συνδέεται και λαμβάνει αυτόματα updates όταν ο
    Celery worker αλλάζει το status του environment.

    Message format (JSON):
      {
        "status": "Provisioning",
        "message": "Creating namespace...",
        "step": "1/4"
      }
    """
    await manager.connect(websocket, env_id)

    # Στέλνουμε ένα αρχικό "connected" message
    await websocket.send_json({
        "status": "Connected",
        "message": f"Watching environment {env_id}",
        "step": "0/4",
    })

    try:
        # Τρέχουμε παράλληλα:
        # 1. redis_listener: ακούει Redis και forward-αρει στο WebSocket
        # 2. receive loop: διατηρεί το connection ζωντανό (ping/pong)
        listener_task = asyncio.create_task(redis_listener(env_id, websocket))

        try:
            while True:
                # Διαβάζουμε από τον client (π.χ. ping frames) για να μην κλείσει το connection
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    finally:
        manager.disconnect(websocket, env_id)
