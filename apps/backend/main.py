import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.api import endpoints, websockets

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Internal Developer Platform API — self-service environments on Kubernetes",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(endpoints.router)
app.include_router(websockets.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Θα περιοριστεί σε production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    """Δημιουργεί τα tables αν δεν υπάρχουν (development only — production χρησιμοποιεί Alembic)."""
    logger.info("Starting up IDP Platform API...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Shutting down IDP Platform API...")
    await engine.dispose()


@app.get("/healthz", tags=["Health"])
async def healthz():
    """Health check endpoint — χρησιμοποιείται από K8s liveness probe."""
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/readyz", tags=["Health"])
async def readyz():
    """
    Readiness probe — ελέγχει αν η εφαρμογή είναι έτοιμη να δεχθεί traffic.
    Κάνει πραγματικό SELECT 1 στη PostgreSQL.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        from fastapi import Response
        return Response(
            content='{"status": "not ready", "db": "unreachable"}',
            status_code=503,
            media_type="application/json",
        )
