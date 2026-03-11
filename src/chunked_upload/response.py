from django.http import HttpResponse

from .settings import CONTENT_TYPE, ENCODER


class Response(HttpResponse):
    """JSON-encoded HttpResponse using the configured encoder."""

    def __init__(self, content, status=None, **kwargs):
        super().__init__(
            content=ENCODER(content),
            content_type=CONTENT_TYPE,
            status=status,
            **kwargs,
        )
