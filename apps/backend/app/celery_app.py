from celery import Celery

from app.config import settings

# Δημιουργία Celery app — χρησιμοποιεί Redis ως broker και result backend
celery_app = Celery(
    "idp_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],  # autodiscover tasks από το tasks module
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task settings
    task_track_started=True,           # το task εμφανίζεται ως STARTED πριν τελειώσει
    task_acks_late=True,               # το task γίνεται acknowledged μόνο μετά την εκτέλεση
    worker_prefetch_multiplier=1,      # ένα task τη φορά ανά worker (σημαντικό για long-running tasks)

    # Result expiry — τα results διαγράφονται από Redis μετά από 1 ώρα
    result_expires=3600,

    # Retry policy
    task_default_retry_delay=10,       # 10 δευτερόλεπτα μεταξύ retries
    task_max_retries=3,
)
