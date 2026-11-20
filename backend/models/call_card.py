"""Carta de Llamada derivada por el operador."""

from __future__ import annotations

from django.db import models

from backend.choices import Category, Priority


class CallCard(models.Model):
    """Carta de Llamada validada por el operador y derivada al despacho."""

    created_at = models.DateTimeField(auto_now_add=True)
    transcript = models.TextField()
    street = models.CharField(max_length=160)
    street_number = models.CharField(max_length=32, blank=True)
    intersection = models.CharField(max_length=160, blank=True)
    neighborhood = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=32, choices=Category.choices)
    subcategory = models.CharField(max_length=160)
    priority = models.CharField(max_length=2, choices=Priority.choices)
    answered_questions = models.JSONField(default=list)
    pending_questions = models.JSONField(default=list)
    # Subconjunto de las preguntas respondidas/pendientes que propuso el LLM (no son del protocolo).
    ai_suggested_questions = models.JSONField(default=list, blank=True)
    instructions_given = models.JSONField(default=list)  # instrucciones pre-arribo leídas al llamante
    risks = models.JSONField(default=list)
    suggested_resources = models.TextField(blank=True)
    operator_notes = models.TextField(blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    ai_provider = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"Carta #{self.pk} · {self.priority} · {self.subcategory}"
