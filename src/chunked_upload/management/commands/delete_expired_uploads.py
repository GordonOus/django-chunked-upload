from django.core.management.base import BaseCommand
from django.utils import timezone

from chunked_upload.constants import COMPLETE, UPLOADING
from chunked_upload.models import ChunkedUpload
from chunked_upload.settings import EXPIRATION_DELTA


class Command(BaseCommand):
    help = "Deletes chunked uploads that have already expired."

    model = ChunkedUpload

    def add_arguments(self, parser):
        parser.add_argument(
            "--interactive",
            action="store_true",
            default=False,
            help="Prompt for confirmation before each deletion.",
        )

    def handle(self, *args, **options):
        interactive = options["interactive"]

        count = {UPLOADING: 0, COMPLETE: 0}
        queryset = self.model.objects.filter(
            created_on__lt=(timezone.now() - EXPIRATION_DELTA)
        )

        for chunked_upload in queryset:
            if interactive:
                prompt = f"Do you want to delete {chunked_upload}? (y/n): "
                answer = input(prompt).lower()
                while answer not in ("y", "n"):
                    answer = input(prompt).lower()
                if answer == "n":
                    continue

            count[chunked_upload.status] += 1
            chunked_upload.delete()

        self.stdout.write(f"{count[COMPLETE]} complete uploads were deleted.")
        self.stdout.write(f"{count[UPLOADING]} incomplete uploads were deleted.")
