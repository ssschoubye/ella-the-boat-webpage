from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

THUMBNAIL_SIZE = (480, 480)


def make_thumbnail(archive_file):
    """Store a small JPEG of an uploaded image as archive_file.thumbnail.

    Returns False, leaving the thumbnail empty, if Pillow can't read the file;
    the grid then shows the extension badge instead.
    """
    try:
        with archive_file.file.open("rb") as fh, Image.open(fh) as image:
            # Phone photos are often stored sideways with an EXIF rotation.
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail(THUMBNAIL_SIZE)
            buffer = BytesIO()
            image.save(buffer, "JPEG", quality=80)
    except (OSError, ValueError, Image.DecompressionBombError):
        return False

    archive_file.thumbnail.save("miniature.jpg", ContentFile(buffer.getvalue()), save=True)
    return True
