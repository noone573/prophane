from unittest import mock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase

from .models import PropaneTank, Store
from .storage import SupabaseStorage


def fake_response(status=200, json=None, content=b'', headers=None):
    resp = mock.Mock(status_code=status, content=content, text='', headers=headers or {})
    resp.json.return_value = json or {}
    return resp


class SupabaseStorageTests(TestCase):
    def setUp(self):
        self.storage = SupabaseStorage(url='https://abc.supabase.co/', key='secret', bucket='media')
        self.session = mock.Mock()
        self.storage._session = self.session

    def test_save_uploads_to_bucket_with_unique_name(self):
        self.session.post.return_value = fake_response(200)
        name = self.storage.save('store_owners/me.png', ContentFile(b'img'))

        self.assertRegex(name, r'^store_owners/me_[0-9a-f]{8}\.png$')
        url = self.session.post.call_args.args[0]
        self.assertEqual(url, f'https://abc.supabase.co/storage/v1/object/media/{name}')
        self.assertEqual(self.session.post.call_args.kwargs['data'], b'img')
        self.assertEqual(self.session.post.call_args.kwargs['headers']['Content-Type'], 'image/png')

    def test_failed_upload_raises(self):
        self.session.post.return_value = fake_response(400)
        with self.assertRaises(IOError):
            self.storage.save('a.png', ContentFile(b'x'))

    def test_url_is_signed_and_cached(self):
        self.session.post.return_value = fake_response(
            200, json={'signedURL': '/object/sign/media/a.png?token=t'})

        first = self.storage.url('a.png')
        second = self.storage.url('a.png')

        self.assertEqual(first, 'https://abc.supabase.co/storage/v1/object/sign/media/a.png?token=t')
        self.assertEqual(first, second)
        self.assertEqual(self.session.post.call_count, 1)

    def test_url_for_missing_file_does_not_crash(self):
        self.session.post.return_value = fake_response(400)
        self.assertIn('/object/media/gone.png', self.storage.url('gone.png'))

    def test_open_and_delete(self):
        self.session.get.return_value = fake_response(200, content=b'data')
        self.assertEqual(self.storage.open('docs/id.pdf').read(), b'data')

        self.storage.delete('docs/id.pdf')
        self.assertEqual(self.session.delete.call_args.kwargs['json'], {'prefixes': ['docs/id.pdf']})

    def test_ensure_bucket_creates_private_bucket_once(self):
        self.session.get.return_value = fake_response(404)
        self.session.post.return_value = fake_response(200)
        self.assertTrue(self.storage.ensure_bucket())
        self.assertEqual(self.session.post.call_args.kwargs['json']['public'], False)

        self.session.get.return_value = fake_response(200)
        self.assertFalse(self.storage.ensure_bucket())


class SeedShopsTests(TestCase):
    def test_seed_shops_is_repeatable(self):
        call_command('seed_shops', stdout=mock.Mock())
        call_command('seed_shops', stdout=mock.Mock())

        seller = User.objects.get(username='demo_seller')
        self.assertFalse(seller.has_usable_password())
        self.assertTrue(seller.profile.is_seller())
        self.assertEqual(Store.objects.filter(owner=seller).count(), 5)
        self.assertEqual(PropaneTank.objects.filter(store__owner=seller).count(), 12)

    def test_seeded_shops_show_on_map(self):
        call_command('seed_shops', stdout=mock.Mock())
        user = User.objects.create_user('buyer', password='pw-123456')
        self.client.force_login(user)

        resp = self.client.get('/map/')

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Juan")
        self.assertContains(resp, 'img/default.png')
