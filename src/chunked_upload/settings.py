import os.path
import time
from datetime import timedelta

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.module_loading import import_string

# How long after creation the upload will expire
DEFAULT_EXPIRATION_DELTA = timedelta(days=1)
EXPIRATION_DELTA = getattr(
    settings, "CHUNKED_UPLOAD_EXPIRATION_DELTA", DEFAULT_EXPIRATION_DELTA
)

# Path where uploading files will be stored until completion
DEFAULT_UPLOAD_PATH = "chunked_uploads/%Y/%m/%d"
UPLOAD_PATH = getattr(settings, "CHUNKED_UPLOAD_PATH", DEFAULT_UPLOAD_PATH)


def default_upload_to(instance, filename):
    filename = os.path.join(UPLOAD_PATH, f"{instance.upload_id}.part")
    return time.strftime(filename)


UPLOAD_TO = getattr(settings, "CHUNKED_UPLOAD_TO", default_upload_to)


# Storage system — accepts a callable or a dotted import path string.
# Django 4.2+ FileField accepts a callable for ``storage``, so we resolve
# it eagerly here to keep the model definition simple.
def _resolve_storage():
    raw = getattr(settings, "CHUNKED_UPLOAD_STORAGE_CLASS", None)
    if raw is None:
        return None  # use default storage
    if isinstance(raw, str):
        return import_string(raw)()
    if callable(raw):
        return raw()
    return raw


STORAGE = _resolve_storage()

# Function used to encode response data
ENCODER = getattr(settings, "CHUNKED_UPLOAD_ENCODER", DjangoJSONEncoder().encode)

# Content-Type for the response data
CONTENT_TYPE = getattr(
    settings, "CHUNKED_UPLOAD_CONTENT_TYPE", "application/json"
)

# Max amount of data (in bytes) that can be uploaded. None means no limit.
MAX_BYTES = getattr(settings, "CHUNKED_UPLOAD_MAX_BYTES", None)

# Null / blank settings for the user FK on the default ChunkedUpload model
DEFAULT_MODEL_USER_FIELD_NULL = getattr(
    settings, "CHUNKED_UPLOAD_MODEL_USER_FIELD_NULL", True
)
DEFAULT_MODEL_USER_FIELD_BLANK = getattr(
    settings, "CHUNKED_UPLOAD_MODEL_USER_FIELD_BLANK", True
)
