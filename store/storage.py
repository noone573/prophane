"""
Django file storage backed by Supabase Storage.

Uploaded files (store owner photos, seller documents, pickup proofs) are kept
in a private Supabase bucket instead of Render's disk, which is wiped on every
deploy. Files are served through short-lived signed URLs so seller IDs and
permits are never publicly listed.
"""
import mimetypes
import posixpath
import time
import uuid
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class SupabaseStorage(Storage):
    # Signed URLs last an hour; reuse them for most of that time so a page
    # with many photos doesn't make one Supabase request per image every load.
    SIGNED_URL_TTL = 3600
    SIGNED_URL_REUSE = 3000

    def __init__(self, url=None, key=None, bucket=None):
        self.base_url = (url or settings.SUPABASE_URL or '').rstrip('/')
        self.key = key or settings.SUPABASE_KEY
        self.bucket = bucket or settings.SUPABASE_BUCKET
        if not self.base_url or not self.key:
            raise ImproperlyConfigured(
                'SupabaseStorage needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.'
            )
        self._signed_urls = {}
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {self.key}',
            'apikey': self.key,
        })

    # ---------- helpers ----------

    def _api(self, path):
        return f'{self.base_url}/storage/v1/{path}'

    def _object_path(self, name):
        return f'{self.bucket}/{quote(name)}'

    def _clean(self, name):
        return name.replace('\\', '/').lstrip('/')

    # ---------- Storage API ----------

    def _open(self, name, mode='rb'):
        name = self._clean(name)
        resp = self._session.get(self._api(f'object/authenticated/{self._object_path(name)}'), timeout=30)
        if resp.status_code != 200:
            raise FileNotFoundError(f'{name} not found in Supabase bucket {self.bucket}')
        f = ContentFile(resp.content)
        f.name = name
        return f

    def _save(self, name, content):
        name = self._clean(name)
        content.seek(0)
        content_type = (
            getattr(content, 'content_type', None)
            or mimetypes.guess_type(name)[0]
            or 'application/octet-stream'
        )
        resp = self._session.post(
            self._api(f'object/{self._object_path(name)}'),
            data=content.read(),
            headers={'Content-Type': content_type, 'x-upsert': 'false'},
            timeout=60,
        )
        if resp.status_code not in (200, 201):
            raise IOError(f'Supabase upload failed ({resp.status_code}): {resp.text}')
        return name

    def get_available_name(self, name, max_length=None):
        # Add a short random suffix instead of asking Supabase whether the
        # name is taken; uploads never overwrite each other this way.
        name = self._clean(name)
        dir_name, file_name = posixpath.split(name)
        root, ext = posixpath.splitext(file_name)
        suffix = uuid.uuid4().hex[:8]
        if max_length is not None:
            room = max_length - len(dir_name) - len(ext) - len(suffix) - 2
            root = root[:max(room, 1)]
        return posixpath.join(dir_name, f'{root}_{suffix}{ext}')

    def delete(self, name):
        name = self._clean(name)
        self._session.delete(
            self._api(f'object/{self.bucket}'),
            json={'prefixes': [name]},
            timeout=30,
        )
        self._signed_urls.pop(name, None)

    def exists(self, name):
        name = self._clean(name)
        resp = self._session.head(self._api(f'object/authenticated/{self._object_path(name)}'), timeout=30)
        return resp.status_code == 200

    def size(self, name):
        name = self._clean(name)
        resp = self._session.head(self._api(f'object/authenticated/{self._object_path(name)}'), timeout=30)
        if resp.status_code != 200:
            raise FileNotFoundError(name)
        return int(resp.headers.get('Content-Length', 0))

    def url(self, name):
        name = self._clean(name)
        cached = self._signed_urls.get(name)
        if cached and cached[1] > time.time():
            return cached[0]
        resp = self._session.post(
            self._api(f'object/sign/{self._object_path(name)}'),
            json={'expiresIn': self.SIGNED_URL_TTL},
            timeout=30,
        )
        if resp.status_code != 200:
            # Missing or broken file: return a URL that 404s rather than
            # crashing the whole page.
            return self._api(f'object/{self._object_path(name)}')
        signed = resp.json().get('signedURL') or resp.json().get('signedUrl')
        full = f'{self.base_url}/storage/v1{signed}'
        self._signed_urls[name] = (full, time.time() + self.SIGNED_URL_REUSE)
        return full

    def ensure_bucket(self):
        """Create the private bucket if it doesn't exist yet. Returns True if created."""
        resp = self._session.get(self._api(f'bucket/{self.bucket}'), timeout=30)
        if resp.status_code == 200:
            return False
        resp = self._session.post(
            self._api('bucket'),
            json={'id': self.bucket, 'name': self.bucket, 'public': False},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise IOError(f'Could not create Supabase bucket {self.bucket} ({resp.status_code}): {resp.text}')
        return True
