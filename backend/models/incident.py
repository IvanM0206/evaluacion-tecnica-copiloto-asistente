from __future__ import annotations

from django.db import models

from backend.choices import Category, IncidentSource, Priority


class Incident(models.Model):
    """A documented call: the provided CSV rows plus any future synthetic data.

    Used by the services layer as the reference catalog (retrieval, few-shot,
    protocol questions, pre-arrival instructions).
    """

    external_id = models.CharField(max_length=64, unique=True)  # id_registro
    source = models.CharField(max_length=16, choices=IncidentSource.choices, default=IncidentSource.DATASET)
    called_at = models.DateTimeField(null=True, blank=True)  # timestamp_llamada
    origin = models.CharField(max_length=32)  # TELEFONIA_911, APP_CIUDADANA, ...
    category = models.CharField(max_length=32, choices=Category.choices)
    subcategory = models.CharField(max_length=160)
    priority = models.CharField(max_length=2, choices=Priority.choices)
    transcript = models.TextField()
    street = models.CharField(max_length=160, blank=True)
    street_number = models.CharField(max_length=32, blank=True)
    intersection = models.CharField(max_length=160, blank=True)
    neighborhood = models.CharField(max_length=160, blank=True)
    mandatory_questions = models.JSONField(default=list)
    answered_questions = models.JSONField(default=list)
    pending_questions = models.JSONField(default=list)
    pre_arrival_instructions = models.TextField(blank=True)
    risks = models.JSONField(default=list)
    resources = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["external_id"]

    def __str__(self) -> str:
        return f"{self.external_id} · {self.subcategory}"
