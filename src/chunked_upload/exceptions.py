class ChunkedUploadError(Exception):
    """Exception raised for errors in the chunked upload request/process."""

    def __init__(self, status: int, **data):
        self.status_code = status
        self.data = data
