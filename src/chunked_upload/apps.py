from django.apps import AppConfig


class ChunkedUploadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chunked_upload"
    verbose_name = "Chunked Uploads"
