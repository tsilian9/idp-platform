"""
Celery tasks για async provisioning/deprovisioning environments.

Flow:
  1. FastAPI endpoint δέχεται request → αποθηκεύει Environment στη DB (status=Pending)
  2. Στέλνει task στο Redis broker
  3. Celery worker εκτελεί το task:
     a. Κάνει commit το Environment CR στο GitOps repo
     b. ArgoCD κάνει sync → δημιουργεί το CR στο K8s
     c. Ο K8s Operator το βλέπει και κάνει reconcile (namespace, RBAC, κτλ)
     d. Ο Operator ενημερώνει το status → Ready ή Failed
"""
import json
import logging

from celery import Task

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class BaseTaskWithRetry(Task):
    """Base task class με αυτόματο retry σε exceptions."""
    abstract = True
    max_retries = 3
    default_retry_delay = 10


@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="tasks.provision_environment",
)
def provision_environment(self, environment_id: str, environment_name: str, owner: str, tier: str, database: bool) -> dict:
    """
    Κάνει provision ένα νέο environment.

    Args:
        environment_id: UUID του Environment στη DB
        environment_name: Όνομα του environment (γίνεται K8s namespace)
        owner: Email του developer
        tier: dev | staging | prod
        database: Αν θέλει PostgreSQL στο namespace του

    Returns:
        dict με το αποτέλεσμα του task
    """
    logger.info(
        "Starting provisioning for environment '%s' (id=%s, owner=%s, tier=%s)",
        environment_name, environment_id, owner, tier,
    )

    try:
        # TODO (Task 2.7): Commit Environment CR στο GitOps repo μέσω GitHub API
        # Προς το παρόν log μόνο — θα υλοποιηθεί στο Task 2.7
        logger.info(
            "TODO: Commit Environment CR to GitOps repo for '%s'", environment_name
        )

        return {
            "status": "success",
            "environment_id": environment_id,
            "environment_name": environment_name,
            "message": "GitOps commit queued — ArgoCD will sync shortly",
        }

    except Exception as exc:
        logger.error(
            "Failed to provision environment '%s': %s", environment_name, exc
        )
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=BaseTaskWithRetry,
    name="tasks.deprovision_environment",
)
def deprovision_environment(self, environment_id: str, environment_name: str) -> dict:
    """
    Κάνει deprovision (διαγράφει) ένα environment.

    Args:
        environment_id: UUID του Environment στη DB
        environment_name: Όνομα του environment

    Returns:
        dict με το αποτέλεσμα του task
    """
    logger.info(
        "Starting deprovisioning for environment '%s' (id=%s)",
        environment_name, environment_id,
    )

    try:
        # TODO (Task 2.7): Διαγραφή Environment CR από το GitOps repo
        logger.info(
            "TODO: Delete Environment CR from GitOps repo for '%s'", environment_name
        )

        return {
            "status": "success",
            "environment_id": environment_id,
            "environment_name": environment_name,
            "message": "GitOps delete committed — ArgoCD will sync shortly",
        }

    except Exception as exc:
        logger.error(
            "Failed to deprovision environment '%s': %s", environment_name, exc
        )
        raise self.retry(exc=exc)
