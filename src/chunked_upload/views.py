import re

from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import View

from .constants import COMPLETE, HttpStatus
from .exceptions import ChunkedUploadError
from .models import ChunkedUpload
from .response import Response
from .settings import MAX_BYTES


class ChunkedUploadBaseView(View):
    """Base view for chunked upload views."""

    model = ChunkedUpload
    user_field_name = "user"

    def get_queryset(self, request):
        """
        Get (and filter) ChunkedUpload queryset.
        By default, users can only continue uploading their own uploads.
        """
        queryset = self.model.objects.all()
        if (
            hasattr(self.model, self.user_field_name)
            and hasattr(request, "user")
            and request.user.is_authenticated
        ):
            queryset = queryset.filter(**{self.user_field_name: request.user})
        return queryset

    def validate(self, request):
        """
        Placeholder method for extra validation.
        Must raise ChunkedUploadError if validation fails.
        """

    def get_response_data(self, chunked_upload, request):
        """Data for the response. Called only if POST is successful."""
        return {}

    def pre_save(self, chunked_upload, request, new=False):
        """Called before saving."""

    def save(self, chunked_upload, request, new=False):
        """Persist the chunked upload instance."""
        chunked_upload.save()

    def post_save(self, chunked_upload, request, new=False):
        """Called after saving."""

    def _save(self, chunked_upload):
        new = chunked_upload.id is None
        self.pre_save(chunked_upload, self.request, new=new)
        self.save(chunked_upload, self.request, new=new)
        self.post_save(chunked_upload, self.request, new=new)

    def check_permissions(self, request):
        """Grants permission to start/continue an upload."""
        if hasattr(request, "user") and not request.user.is_authenticated:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_403_FORBIDDEN,
                detail="Authentication credentials were not provided",
            )

    def _post(self, request, *args, **kwargs):
        raise NotImplementedError

    def post(self, request, *args, **kwargs):
        try:
            self.check_permissions(request)
            return self._post(request, *args, **kwargs)
        except ChunkedUploadError as error:
            return Response(error.data, status=error.status_code)


class ChunkedUploadView(ChunkedUploadBaseView):
    """
    Uploads large files in multiple chunks with the ability to resume
    if the upload is interrupted.
    """

    field_name = "file"
    content_range_header = "HTTP_CONTENT_RANGE"
    content_range_pattern = re.compile(
        r"^bytes (?P<start>\d+)-(?P<end>\d+)/(?P<total>\d+)$"
    )
    max_bytes = MAX_BYTES
    fail_if_no_header = False

    def get_extra_attrs(self, request):
        """Extra attributes for a new ChunkedUpload instance."""
        attrs = {}
        if (
            hasattr(self.model, self.user_field_name)
            and hasattr(request, "user")
            and request.user.is_authenticated
        ):
            attrs[self.user_field_name] = request.user
        return attrs

    def get_max_bytes(self, request):
        """Override to provide per-user upload limits."""
        return self.max_bytes

    def create_chunked_upload(self, save=False, **attrs):
        """Create a new chunked upload instance with an empty file."""
        chunked_upload = self.model(**attrs)
        chunked_upload.file.save(name="tmp", content=ContentFile(b""), save=save)
        return chunked_upload

    def is_valid_chunked_upload(self, chunked_upload):
        """Check if chunked upload has expired or is already complete."""
        if chunked_upload.expired:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_410_GONE, detail="Upload has expired"
            )
        if chunked_upload.status == COMPLETE:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail='Upload has already been marked as "complete"',
            )

    def get_response_data(self, chunked_upload, request):
        return {
            "upload_id": chunked_upload.upload_id,
            "offset": chunked_upload.offset,
            "expires": chunked_upload.expires_on,
        }

    def _post(self, request, *args, **kwargs):
        chunk = request.FILES.get(self.field_name)
        if chunk is None:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail="No chunk file was submitted",
            )
        self.validate(request)

        upload_id = request.POST.get("upload_id")
        if upload_id:
            chunked_upload = get_object_or_404(
                self.get_queryset(request), upload_id=upload_id
            )
            self.is_valid_chunked_upload(chunked_upload)
        else:
            attrs = {"filename": chunk.name}
            attrs.update(self.get_extra_attrs(request))
            chunked_upload = self.create_chunked_upload(save=False, **attrs)

        content_range = request.META.get(self.content_range_header, "")
        match = self.content_range_pattern.match(content_range)
        if match:
            start = int(match.group("start"))
            end = int(match.group("end"))
            total = int(match.group("total"))
        elif self.fail_if_no_header:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail="Error in request headers",
            )
        else:
            start = 0
            end = chunk.size - 1
            total = chunk.size

        chunk_size = end - start + 1
        max_bytes = self.get_max_bytes(request)

        if max_bytes is not None and total > max_bytes:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail=f"Size of file exceeds the limit ({max_bytes} bytes)",
            )
        if chunked_upload.offset != start:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail="Offsets do not match",
                offset=chunked_upload.offset,
            )
        if chunk.size != chunk_size:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail="File size doesn't match headers",
            )

        chunked_upload.append_chunk(chunk, chunk_size=chunk_size, save=False)
        self._save(chunked_upload)

        return Response(
            self.get_response_data(chunked_upload, request),
            status=HttpStatus.HTTP_200_OK,
        )


class ChunkedUploadCompleteView(ChunkedUploadBaseView):
    """
    Completes a chunked upload. Override ``on_completion`` to define
    what happens when the upload is complete.
    """

    do_md5_check = True

    def on_completion(self, uploaded_file, request):
        """Placeholder — define what to do when upload is complete."""

    def is_valid_chunked_upload(self, chunked_upload):
        if chunked_upload.status == COMPLETE:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail="Upload has already been marked as complete",
            )

    def md5_check(self, chunked_upload, md5):
        if chunked_upload.md5 != md5:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST,
                detail="md5 checksum does not match",
            )

    def _post(self, request, *args, **kwargs):
        upload_id = request.POST.get("upload_id")
        md5 = request.POST.get("md5")

        error_msg = None
        if self.do_md5_check:
            if not upload_id or not md5:
                error_msg = "Both 'upload_id' and 'md5' are required"
        elif not upload_id:
            error_msg = "'upload_id' is required"
        if error_msg:
            raise ChunkedUploadError(
                status=HttpStatus.HTTP_400_BAD_REQUEST, detail=error_msg
            )

        chunked_upload = get_object_or_404(
            self.get_queryset(request), upload_id=upload_id
        )

        self.validate(request)
        self.is_valid_chunked_upload(chunked_upload)
        if self.do_md5_check:
            self.md5_check(chunked_upload, md5)

        chunked_upload.status = COMPLETE
        chunked_upload.completed_on = timezone.now()
        self._save(chunked_upload)
        self.on_completion(chunked_upload.get_uploaded_file(), request)

        return Response(
            self.get_response_data(chunked_upload, request),
            status=HttpStatus.HTTP_200_OK,
        )
