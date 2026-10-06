import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditLog(Base):
    """
    Καταγράφει κάθε ενέργεια που γίνεται σε ένα Environment.

    Χρησιμοποιείται για audit trail — ποιος έκανε τι και πότε.
    Παραδείγματα actions: 'environment.created', 'environment.deleted',
    'status.changed', 'provision.started', 'provision.completed'.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key στο Environment — CASCADE delete (αν σβηστεί το env, σβήνουν και τα logs)
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Η ενέργεια που έγινε (π.χ. 'environment.created', 'status.changed')
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Ποιος έκανε την ενέργεια (email του developer ή 'system' για αυτόματες ενέργειες)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)

    # Πότε έγινε η ενέργεια
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Επιπλέον πληροφορίες (π.χ. JSON string με old_status/new_status)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship πίσω στο Environment
    environment: Mapped["Environment"] = relationship(
        "Environment",
        back_populates="audit_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action!r}, "
            f"actor={self.actor!r}, environment_id={self.environment_id})>"
        )
