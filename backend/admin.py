from django.contrib import admin

from backend.models import CallCard, Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("external_id", "source", "category", "subcategory", "priority", "street", "street_number")
    list_filter = ("source", "category", "priority", "origin")
    search_fields = ("external_id", "subcategory", "transcript", "street")


@admin.register(CallCard)
class CallCardAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "priority", "category", "subcategory", "street", "street_number", "ai_provider")
    list_filter = ("priority", "category")
