from django.contrib import admin

from .models import ChunkedUpload


@admin.register(ChunkedUpload)
class ChunkedUploadAdmin(admin.ModelAdmin):
    list_display = ("upload_id", "filename", "status", "created_on")
    search_fields = ("upload_id", "filename")
    list_filter = ("status",)
