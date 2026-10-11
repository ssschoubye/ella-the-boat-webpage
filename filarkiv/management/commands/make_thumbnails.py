from django.core.management.base import BaseCommand

from filarkiv.models import ArchiveFile
from filarkiv.thumbnails import make_thumbnail


class Command(BaseCommand):
    help = "Make thumbnails for images in the file archive that have none."

    def handle(self, *args, **options):
        made = failed = 0
        for archive_file in ArchiveFile.objects.filter(thumbnail=""):
            if not archive_file.is_image:
                continue
            if make_thumbnail(archive_file):
                made += 1
            else:
                failed += 1
                self.stderr.write(f"Kunne ikke læse {archive_file.file.name}")
        self.stdout.write(f"{made} miniaturer lavet, {failed} fejlede.")
