# django-chunked-upload

Upload large files to Django in multiple chunks, with the ability to resume if the
upload is interrupted.

Modernized fork of [django-chunked-upload](https://github.com/GordonOus/django-chunked-upload)
for **Django 5.x+** and **Python 3.10+**.

## Requirements

- Python >= 3.10
- Django >= 5.0

## Installation

### From PyPI (when published)

```bash
pip install django-chunked-upload
```

### From local path

```bash
pip install -e /path/to/packages/django-chunked-upload
```

### From git

```bash
pip install git+https://github.com/careconekt/django-chunked-upload.git
```

## Setup

### 1. Add to `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    # ...
    "chunked_upload",
]
```

### 2. Run migrations

```bash
python manage.py makemigrations chunked_upload
python manage.py migrate
```

### 3. Add URL routes

```python
from chunked_upload.views import ChunkedUploadView, ChunkedUploadCompleteView

urlpatterns = [
    path("api/chunked-upload/", ChunkedUploadView.as_view(), name="chunked-upload"),
    path("api/chunked-upload-complete/", ChunkedUploadCompleteView.as_view(), name="chunked-upload-complete"),
]
```

## How It Works

### Phase 1 — Upload chunks

```
POST /api/chunked-upload/
Content-Range: bytes 0-999999/5000000
Body: file=<chunk>
```

First request (no `upload_id`) creates the upload session. Subsequent requests
include the `upload_id` from the response. Each response returns:

```json
{
    "upload_id": "a1b2c3d4...",
    "offset": 1000000,
    "expires": "2026-03-12T14:30:00Z"
}
```

### Phase 2 — Complete

```
POST /api/chunked-upload-complete/
Body: upload_id=a1b2c3d4...&md5=<hex_digest>
```

Server verifies the MD5 checksum and marks the upload as complete.

### Resume

If interrupted, resume by sending the next chunk with the same `upload_id`. The
server validates that the offset matches where it left off.

## Usage

### Basic

```python
from chunked_upload.views import ChunkedUploadView, ChunkedUploadCompleteView


class MyUploadView(ChunkedUploadView):
    pass


class MyUploadCompleteView(ChunkedUploadCompleteView):
    def on_completion(self, uploaded_file, request):
        # Process the completed file
        pass
```

### Custom model

```python
from django.conf import settings
from django.db import models
from chunked_upload.models import AbstractChunkedUpload


class MyChunkedUpload(AbstractChunkedUpload):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=50)
```

Then point your views to the custom model:

```python
class MyUploadView(ChunkedUploadView):
    model = MyChunkedUpload
```

### Anonymous uploads

```python
class AnonymousUploadView(ChunkedUploadView):
    def check_permissions(self, request):
        pass  # skip auth check
```

### Per-user size limits

```python
class LimitedUploadView(ChunkedUploadView):
    def get_max_bytes(self, request):
        if request.user.is_staff:
            return None  # unlimited
        return 100 * 1024 * 1024  # 100 MB
```

## Settings

All optional. Add to your Django `settings.py` to override defaults.

| Setting | Default | Description |
|---------|---------|-------------|
| `CHUNKED_UPLOAD_EXPIRATION_DELTA` | `timedelta(days=1)` | Time before incomplete uploads expire |
| `CHUNKED_UPLOAD_PATH` | `"chunked_uploads/%Y/%m/%d"` | Upload directory (supports strftime) |
| `CHUNKED_UPLOAD_TO` | `default_upload_to` | Custom `upload_to` callable |
| `CHUNKED_UPLOAD_STORAGE_CLASS` | `None` | Storage backend (dotted path or callable) |
| `CHUNKED_UPLOAD_ENCODER` | `DjangoJSONEncoder().encode` | JSON encoder for responses |
| `CHUNKED_UPLOAD_CONTENT_TYPE` | `"application/json"` | Response content type |
| `CHUNKED_UPLOAD_MAX_BYTES` | `None` (no limit) | Maximum total file size |
| `CHUNKED_UPLOAD_MODEL_USER_FIELD_NULL` | `True` | Allow NULL on user FK |
| `CHUNKED_UPLOAD_MODEL_USER_FIELD_BLANK` | `True` | Allow blank on user FK |

## Management Commands

```bash
# Delete expired uploads
python manage.py delete_expired_uploads

# With confirmation prompts
python manage.py delete_expired_uploads --interactive
```

## Client-Side Example

```javascript
const chunkSize = 2 * 1024 * 1024; // 2 MB
let uploadId = null;

async function uploadFile(file) {
    const totalChunks = Math.ceil(file.size / chunkSize);

    for (let i = 0; i < totalChunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(start + chunkSize, file.size);
        const formData = new FormData();
        formData.append("file", file.slice(start, end), file.name);
        if (uploadId) formData.append("upload_id", uploadId);

        const res = await fetch("/api/chunked-upload/", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Range": `bytes ${start}-${end - 1}/${file.size}`,
            },
            body: formData,
        });
        const data = await res.json();
        uploadId = data.upload_id;
        console.log(`Progress: ${Math.round((data.offset / file.size) * 100)}%`);
    }

    // Complete with MD5 checksum
    const formData = new FormData();
    formData.append("upload_id", uploadId);
    formData.append("md5", await computeMD5(file));
    await fetch("/api/chunked-upload-complete/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
    });
}
```

## License

MIT-0
