from django.contrib import admin

from backend.models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("external_id", "source", "category", "subcategory", "priority", "street", "street_number")
    list_filter = ("source", "category", "priority", "origin")
    search_fields = ("external_id", "subcategory", "transcript", "street")
