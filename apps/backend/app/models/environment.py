import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnvironmentStatus(str, enum.Enum):
    """Τα πιθανά states ενός Environment — αντικατοπτρίζει το CRD status.phase."""
    PENDING = "Pending"
    PROVISIONING = "Provisioning"
    READY = "Ready"
    FAILED = "Failed"
    DELETING = "Deleting"


class EnvironmentTier(str, enum.Enum):
    """Tier του environment — αντικατοπτρίζει το CRD spec.tier."""
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Environment(Base):
    """
    Αντιπροσωπεύει ένα developer environment.

    Αποθηκεύει το state του environment στην PostgreSQL.
    Ο Kubernetes Operator διαχειρίζεται το αντίστοιχο CRD στο cluster.
    """
    __tablename__ = "environments"

    # Primary key — UUID για να μην εκθέτουμε sequential IDs
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Το όνομα της εφαρμογής (π.χ. "my-service") — γίνεται και το K8s namespace name
    name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True, index=True)

    # Ο developer που έκανε το request
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Tier: dev | staging | prod
    tier: Mapped[EnvironmentTier] = mapped_column(
        Enum(EnvironmentTier, name="environment_tier"),
        nullable=False,
        default=EnvironmentTier.DEV,
    )

    # Status: Pending | Provisioning | Ready | Failed | Deleting
    status: Mapped[EnvironmentStatus] = mapped_column(
        Enum(EnvironmentStatus, name="environment_status"),
        nullable=False,
        default=EnvironmentStatus.PENDING,
        index=True,
    )

    # Αν θέλει database (PostgreSQL) στο namespace του
    database_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Αριθμός replicas για την εφαρμογή
    replicas: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Το K8s namespace που δημιουργήθηκε (γεμίζει από τον Operator)
    namespace: Mapped[str | None] = mapped_column(String(63), nullable=True)

    # Μήνυμα για τον developer (π.χ. error message αν Failed)
    message: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Timestamps — βάζει αυτόματα η PostgreSQL
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship με AuditLog — ένα environment έχει πολλά audit logs
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="environment",
        cascade="all, delete-orphan",
        order_by="AuditLog.timestamp.desc()",
    )

    def __repr__(self) -> str:
        return f"<Environment(id={self.id}, name={self.name!r}, status={self.status})>"
