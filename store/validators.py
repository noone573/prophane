"""Upload checks shared by forms and views.

File extensions and browser-supplied content types are easy to fake, so every
upload is also checked by its leading bytes, and images are opened with Pillow.
"""
import os
import uuid

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
DOCUMENT_EXTENSIONS = IMAGE_EXTENSIONS | {'pdf'}

_SIGNATURES = {
    'pdf': (b'%PDF-',),
    'png': (b'\x89PNG\r\n\x1a\n',),
    'jpg': (b'\xff\xd8\xff',),
    'jpeg': (b'\xff\xd8\xff',),
}


def _extension(name):
    return os.path.splitext(name or '')[1].lstrip('.').lower()


def _read_head(upload, size=16):
    pos = upload.tell() if hasattr(upload, 'tell') else 0
    upload.seek(0)
    head = upload.read(size)
    upload.seek(pos)
    return head


def validate_upload(upload, allowed_extensions):
    if upload is None:
        return
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError('File must be 5 MB or smaller.')

    ext = _extension(upload.name)
    if ext not in allowed_extensions:
        allowed = ', '.join(sorted(e.upper() for e in allowed_extensions))
        raise ValidationError(f'Unsupported file type. Use {allowed}.')

    head = _read_head(upload)
    if not any(head.startswith(sig) for sig in _SIGNATURES[ext]):
        raise ValidationError('The file content does not match its extension.')

    if ext in IMAGE_EXTENSIONS:
        try:
            upload.seek(0)
            with Image.open(upload) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise ValidationError('The image appears to be damaged or invalid.')
        finally:
            upload.seek(0)


def validate_image_upload(upload):
    validate_upload(upload, IMAGE_EXTENSIONS)


def validate_document_upload(upload):
    validate_upload(upload, DOCUMENT_EXTENSIONS)


@deconstructible
class RandomFilename:
    """upload_to callable that drops the user's original filename.

    Original names can contain personal details (e.g. "juan_dela_cruz_id.jpg")
    and odd characters, so files are stored under a random name instead.
    """

    def __init__(self, folder):
        self.folder = folder.rstrip('/')

    def __call__(self, instance, filename):
        ext = _extension(filename) or 'bin'
        return f'{self.folder}/{uuid.uuid4().hex}.{ext}'

    def __eq__(self, other):
        return isinstance(other, RandomFilename) and other.folder == self.folder
