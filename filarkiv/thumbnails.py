from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

THUMBNAIL_SIZE = (480, 480)

# Decoding holds the raw bitmap several times over -- exif_transpose, then
# convert("RGB") -- so the pixel count is checked before the first decode.
# Pillow's own bomb check is no help here: it only raises above twice its
# MAX_IMAGE_PIXELS, about 179 Mpixels, and between one and two times it just
# warns and decodes anyway. A flat-colour 13000x13000 PNG is 169 Mpixels and
# compresses to well under the 25 MB upload limit. 60 Mpixels clears a 48 MP
# phone camera with room to spare.
MAX_PIXELS = 60_000_000


def make_thumbnail(archive_file):
    """Store a small JPEG of an uploaded image as archive_file.thumbnail.

    Returns False, leaving the thumbnail empty, if Pillow can't read the file;
    the grid then shows the extension badge instead.
    """
    try:
        with archive_file.file.open("rb") as fh, Image.open(fh) as image:
            # open() has only read the header, so the size is known before
            # any of the pixels are.
            width, height = image.size
            if width * height > MAX_PIXELS:
                return False
            # Phone photos are often stored sideways with an EXIF rotation.
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail(THUMBNAIL_SIZE)
            buffer = BytesIO()
            image.save(buffer, "JPEG", quality=80)
    except (OSError, ValueError, MemoryError, Image.DecompressionBombError):
        return False

    archive_file.thumbnail.save("miniature.jpg", ContentFile(buffer.getvalue()), save=True)
    return True
