from django.db import models


class Priority(models.TextChoices):
    P1 = "P1", "P1 · Riesgo de vida inmediato"
    P2 = "P2", "P2 · Urgente"
    P3 = "P3", "P3 · No urgente"
    P4 = "P4", "P4 · Sin urgencia"


class Category(models.TextChoices):
    INCENDIO_RESCATE = "INCENDIO_RESCATE", "Incendio / Rescate"
    ACCIDENTE_VIAL = "ACCIDENTE_VIAL", "Accidente vial"
    EMERGENCIA_MEDICA = "EMERGENCIA_MEDICA", "Emergencia médica"
    DEFENSA_CIVIL = "DEFENSA_CIVIL", "Defensa civil"
    SERVICIOS_PUBLICOS = "SERVICIOS_PUBLICOS", "Servicios públicos"
    CONVIVENCIA_SEGURIDAD = "CONVIVENCIA_SEGURIDAD", "Convivencia / Seguridad"


class IncidentSource(models.TextChoices):
    """De dónde viene un incidente guardado."""

    DATASET = "DATASET", "Dataset provisto (CSV)"
    SYNTHETIC = "SYNTHETIC", "Sintético / hipotético"
