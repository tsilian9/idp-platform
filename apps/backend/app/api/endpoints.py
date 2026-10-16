import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.environment import Environment, EnvironmentStatus, EnvironmentTier
from app.models.audit_log import AuditLog
from app.tasks.environment_tasks import provision_environment, deprovision_environment

router = APIRouter(prefix='/api/v1', tags=['Environments'])


class EnvironmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=63)
    owner: str = Field(...)
    tier: EnvironmentTier = Field(default=EnvironmentTier.DEV)
    database_enabled: bool = Field(default=False)
    replicas: int = Field(default=1, ge=1, le=10)

    @field_validator('name')
    @classmethod
    def name_must_be_dns_safe(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$', v):
            raise ValueError('Name must be lowercase alphanumeric and hyphens only')
        return v


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    actor: str
    timestamp: str
    details: Optional[str] = None
    model_config = {'from_attributes': True}


class EnvironmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner: str
    tier: EnvironmentTier
    status: EnvironmentStatus
    database_enabled: bool
    replicas: int
    namespace: Optional[str] = None
    message: Optional[str] = None
    created_at: str
    updated_at: str
    model_config = {'from_attributes': True}


class EnvironmentListResponse(BaseModel):
    items: list[EnvironmentResponse]
    total: int
    page: int
    page_size: int

def _env_to_response(env: Environment) -> EnvironmentResponse:
    return EnvironmentResponse(
        id=env.id, name=env.name, owner=env.owner, tier=env.tier,
        status=env.status, database_enabled=env.database_enabled,
        replicas=env.replicas, namespace=env.namespace, message=env.message,
        created_at=env.created_at.isoformat(), updated_at=env.updated_at.isoformat(),
    )


async def _write_audit_log(
    db: AsyncSession, environment_id: uuid.UUID, action: str,
    actor: str, details: Optional[dict] = None,
) -> None:
    log = AuditLog(
        environment_id=environment_id, action=action, actor=actor,
        details=json.dumps(details) if details else None,
    )
    db.add(log)
    await db.flush()


@router.post('/environments', response_model=EnvironmentResponse, status_code=status.HTTP_202_ACCEPTED, summary='Create environment')
async def create_environment(payload: EnvironmentCreateRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Environment).where(Environment.name == payload.name))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Environment '{payload.name}' already exists")
    env = Environment(
        name=payload.name, owner=payload.owner, tier=payload.tier,
        status=EnvironmentStatus.PENDING, database_enabled=payload.database_enabled,
        replicas=payload.replicas,
    )
    db.add(env)
    await db.flush()
    await _write_audit_log(db=db, environment_id=env.id, action='environment.created', actor=payload.owner,
        details={'tier': payload.tier, 'database_enabled': payload.database_enabled})
    provision_environment.delay(
        environment_id=str(env.id), environment_name=env.name,
        owner=env.owner, tier=env.tier.value, database=env.database_enabled,
    )
    return _env_to_response(env)


@router.get('/environments', response_model=EnvironmentListResponse, summary='List environments')
async def list_environments(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    owner: Optional[str] = Query(default=None), tier: Optional[EnvironmentTier] = Query(default=None),
    status_filter: Optional[EnvironmentStatus] = Query(default=None, alias='status'),
    db: AsyncSession = Depends(get_db),
):
    query = select(Environment)
    if owner:
        query = query.where(Environment.owner == owner)
    if tier:
        query = query.where(Environment.tier == tier)
    if status_filter:
        query = query.where(Environment.status == status_filter)
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()
    query = query.order_by(Environment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    envs = result.scalars().all()
    return EnvironmentListResponse(items=[_env_to_response(e) for e in envs], total=total, page=page, page_size=page_size)

@router.get('/environments/{env_id}', response_model=EnvironmentResponse, summary='Get environment')
async def get_environment(env_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Environment).where(Environment.id == env_id))
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Environment '{env_id}' not found")
    return _env_to_response(env)


@router.delete('/environments/{env_id}', status_code=status.HTTP_202_ACCEPTED, summary='Delete environment')
async def delete_environment(env_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Environment).where(Environment.id == env_id))
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Environment '{env_id}' not found")
    if env.status == EnvironmentStatus.DELETING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Environment '{env.name}' is already being deleted")
    previous_status = env.status.value
    env.status = EnvironmentStatus.DELETING
    await db.flush()
    await _write_audit_log(db=db, environment_id=env.id, action='environment.deleted',
        actor='system', details={'previous_status': previous_status})
    deprovision_environment.delay(environment_id=str(env.id), environment_name=env.name)
    return {'message': f"Environment '{env.name}' deletion initiated", 'id': str(env_id)}


@router.get('/environments/{env_id}/logs', response_model=list[AuditLogResponse], summary='Get audit logs')
async def get_environment_logs(
    env_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    env_result = await db.execute(select(Environment).where(Environment.id == env_id))
    if not env_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Environment '{env_id}' not found")
    logs_result = await db.execute(
        select(AuditLog).where(AuditLog.environment_id == env_id)
        .order_by(AuditLog.timestamp.desc()).limit(limit)
    )
    logs = logs_result.scalars().all()
    return [
        AuditLogResponse(id=log.id, action=log.action, actor=log.actor,
            timestamp=log.timestamp.isoformat(), details=log.details)
        for log in logs
    ]
