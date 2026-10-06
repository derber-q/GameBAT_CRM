"""Независимая DB-очередь с поколениями: изменения во время HTTP не теряются."""
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import OfferConnection, SyncJob


def enqueue(integration, kind, key, payload=None, *, actor=None, delay=0):
    now = timezone.now()
    with transaction.atomic():
        SyncJob.objects.filter(key=f"ym:{integration.pk}:{kind}:{key}").update(generation=F("generation"))
        job, created = SyncJob.objects.get_or_create(key=f"ym:{integration.pk}:{kind}:{key}", defaults={
            "integration": integration, "kind": kind, "payload": payload or {}, "actor": actor,
            "run_after": now + timedelta(seconds=delay),
        })
        if not created:
            if job.payload.get("force") and job.state in {"pending", "running"}:
                payload = {**(payload or {}), "force": True}
            # UPDATE сохраняет работающий lease; завершение увидит новое поколение.
            SyncJob.objects.filter(pk=job.pk).update(generation=F("generation") + 1, payload=payload or {},
                                                     actor=actor, run_after=now + timedelta(seconds=delay), last_error="")
            SyncJob.objects.filter(pk=job.pk).exclude(state="running").update(state="pending", attempts=0)
            job.refresh_from_db()
    return job


def enqueue_product(connection_id):
    connection = OfferConnection.objects.select_related("integration").filter(
        pk=connection_id, active=True, managed=True, integration__enabled=True,
    ).first()
    if not connection:
        return
    enqueue(connection.integration, "product", connection.pk, {"connection_id": connection.pk}, delay=3)
    OfferConnection.objects.filter(pk=connection.pk).update(state=OfferConnection.State.QUEUED)


def product_after_commit(connection_id):
    transaction.on_commit(lambda: enqueue_product(connection_id))
