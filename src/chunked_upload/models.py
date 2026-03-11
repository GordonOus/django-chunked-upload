import hashlib
import uuid

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.utils import timezone

from .constants import CHUNKED_UPLOAD_CHOICES, UPLOADING
from .settings import (
    DEFAULT_MODEL_USER_FIELD_BLANK,
    DEFAULT_MODEL_USER_FIELD_NULL,
    EXPIRATION_DELTA,
    STORAGE,
    UPLOAD_TO,
)


def generate_upload_id():
    return uuid.uuid4().hex


class AbstractChunkedUpload(models.Model):
    """
    Base chunked upload model (abstract).
    Inherit from this model to provide your own concrete implementation.
    """

    upload_id = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        default=generate_upload_id,
    )
    file = models.FileField(
        max_length=255,
        upload_to=UPLOAD_TO,
        storage=STORAGE,
    )
    filename = models.CharField(max_length=255)
    offset = models.BigIntegerField(default=0)
    created_on = models.DateTimeField(auto_now_add=True)
    status = models.PositiveSmallIntegerField(
        choices=CHUNKED_UPLOAD_CHOICES, default=UPLOADING
    )
    completed_on = models.DateTimeField(null=True, blank=True)

    @property
    def expires_on(self):
        return self.created_on + EXPIRATION_DELTA

    @property
    def expired(self):
        return self.expires_on <= timezone.now()

    @property
    def md5(self):
        if getattr(self, "_md5", None) is None:
            md5 = hashlib.md5()
            for chunk in self.file.chunks():
                md5.update(chunk)
            self._md5 = md5.hexdigest()
        return self._md5

    def delete(self, delete_file=True, *args, **kwargs):
        storage, path = None, None
        if self.file:
            storage, path = self.file.storage, self.file.path
        super().delete(*args, **kwargs)
        if storage and delete_file:
            storage.delete(path)

    def __str__(self):
        return (
            f"<{self.filename} - upload_id: {self.upload_id} "
            f"- bytes: {self.offset} - status: {self.status}>"
        )

    def append_chunk(self, chunk, chunk_size=None, save=True):
        self.file.close()
        with open(self.file.path, mode="ab") as file_obj:
            file_obj.write(chunk.read())

        if chunk_size is not None:
            self.offset += chunk_size
        elif hasattr(chunk, "size"):
            self.offset += chunk.size
        else:
            self.offset = self.file.size

        self._md5 = None  # clear cached md5
        if save:
            self.save()
        self.file.close()

    def get_uploaded_file(self):
        self.file.close()
        self.file.open(mode="rb")
        return UploadedFile(file=self.file, name=self.filename, size=self.offset)

    def rename_completed_file(self, save=True):
        """
        Rename the underlying storage file from the temporary ``.part``
        name to the original filename.  Uses the storage API so it works
        with any backend (local filesystem, S3, etc.).
        """
        import os

        old_path = self.file.name  # storage-relative path
        if not old_path.endswith(".part"):
            return  # nothing to rename

        directory = os.path.dirname(old_path)
        # Build new name: <upload_id>_<original_filename>
        safe_name = os.path.basename(self.filename)
        new_name = os.path.join(directory, f"{self.upload_id}_{safe_name}")

        storage = self.file.storage
        self.file.close()

        # Read content, save under new name, delete old file
        with storage.open(old_path, "rb") as f:
            content = f.read()

        from django.core.files.base import ContentFile

        actual_name = storage.save(new_name, ContentFile(content))
        storage.delete(old_path)

        self.file.name = actual_name
        if save:
            self.save()

    class Meta:
        abstract = True


class ChunkedUpload(AbstractChunkedUpload):
    """Default concrete chunked upload model with a user foreign key."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chunked_uploads",
        null=DEFAULT_MODEL_USER_FIELD_NULL,
        blank=DEFAULT_MODEL_USER_FIELD_BLANK,
    )
