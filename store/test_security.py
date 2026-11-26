import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Notification, PropaneTank, Reservation, SellerApplication, Store


def png_bytes():
    buf = BytesIO()
    Image.new('RGB', (4, 4), 'orange').save(buf, 'PNG')
    return buf.getvalue()


@override_settings(SECURE_SSL_REDIRECT=False)
class FlowTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.seller = User.objects.create_user('seller', password='pw-12345678!')
        self.seller.profile.role = 'seller'
        self.seller.profile.status = 'approved'
        self.seller.profile.save()
        self.store = Store.objects.create(owner=self.seller, name='Shop', latitude=11.7, longitude=124.4)
        self.tank = PropaneTank.objects.create(store=self.store, tank_type='Price Gas', price=900, stock=3)
        self.buyer = User.objects.create_user('buyer', password='pw-12345678!')
        self.admin = User.objects.create_user('boss', password='pw-12345678!')
        self.admin.profile.role = 'admin'
        self.admin.profile.save()

    def temp_media(self):
        path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, path, True)
        return self.settings(MEDIA_ROOT=path)


class ReservationTests(FlowTestCase):
    def reserve(self, **data):
        payload = {'name': 'Ana Cruz', 'quantity': 1}
        payload.update(data)
        return self.client.post(reverse('reserve_tank', args=[self.tank.id]), payload)

    def test_reserve_takes_quantity_and_locks_price(self):
        self.client.force_login(self.buyer)
        resp = self.reserve(quantity=2)
        order = Reservation.objects.get()
        self.assertRedirects(resp, reverse('receipt', args=[order.id]))
        self.assertEqual(order.quantity, 2)
        self.assertEqual(order.unit_price, 900)
        self.assertEqual(order.total_price, 1800)
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.stock, 1)
        self.assertEqual(Notification.objects.filter(user=self.seller).count(), 1)

    def test_cannot_reserve_more_than_stock(self):
        self.client.force_login(self.buyer)
        self.reserve(quantity=4)
        self.assertFalse(Reservation.objects.exists())
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.stock, 3)

    def test_get_does_not_reserve(self):
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('reserve_tank', args=[self.tank.id]))
        self.assertEqual(resp.status_code, 405)

    def test_inactive_tank_cannot_be_reserved(self):
        self.tank.is_active = False
        self.tank.save()
        self.client.force_login(self.buyer)
        self.reserve()
        self.assertFalse(Reservation.objects.exists())

    def test_seller_cannot_buy_from_own_store(self):
        self.client.force_login(self.seller)
        self.reserve()
        self.assertFalse(Reservation.objects.exists())

    def test_open_order_limit(self):
        self.tank.stock = 50
        self.tank.save()
        self.client.force_login(self.buyer)
        for _ in range(4):
            self.reserve()
        self.assertEqual(Reservation.objects.count(), 3)

    def test_cancel_requires_post_and_returns_stock(self):
        self.client.force_login(self.buyer)
        self.reserve(quantity=2)
        order = Reservation.objects.get()
        url = reverse('cancel_order', args=[order.id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        order.refresh_from_db()
        self.tank.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(self.tank.stock, 3)

    def test_other_users_cannot_see_or_cancel_order(self):
        self.client.force_login(self.buyer)
        self.reserve()
        order = Reservation.objects.get()
        intruder = User.objects.create_user('intruder', password='pw-12345678!')
        self.client.force_login(intruder)
        self.assertEqual(self.client.get(reverse('receipt', args=[order.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('cancel_order', args=[order.id])).status_code, 404)


class AccessTests(FlowTestCase):
    def test_admin_actions_require_post_and_admin(self):
        url = reverse('admin_toggle_store', args=[self.store.id])
        self.client.force_login(self.buyer)
        self.client.post(url)
        self.store.refresh_from_db()
        self.assertTrue(self.store.is_active)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.store.refresh_from_db()
        self.assertFalse(self.store.is_active)

    def test_seller_cannot_manage_someone_elses_store(self):
        other = User.objects.create_user('other', password='pw-12345678!')
        other.profile.role = 'seller'
        other.profile.status = 'approved'
        other.profile.save()
        self.client.force_login(other)
        resp = self.client.get(reverse('manage_store', args=[self.store.id]))
        self.assertEqual(resp.status_code, 404)

    def test_manage_store_rejects_bad_numbers(self):
        self.client.force_login(self.seller)
        self.client.post(reverse('manage_store', args=[self.store.id]), {
            f'price_{self.tank.id}': 'abc', f'stock_{self.tank.id}': '-5', f'active_{self.tank.id}': 'on',
        })
        self.tank.refresh_from_db()
        self.assertEqual(self.tank.stock, 3)

    def test_logout_requires_post(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_pages_render_for_each_role(self):
        order = Reservation.objects.create(user=self.buyer, store=self.store, tank=self.tank, name='Ana')
        pages = {
            self.buyer: ['map', 'my_orders', 'notifications', 'apply_seller'],
            self.seller: ['my_stores', 'create_store'],
            self.admin: ['admin_dashboard', 'admin_applications', 'admin_sellers', 'admin_stores', 'admin_orders'],
        }
        for user, names in pages.items():
            self.client.force_login(user)
            for name in names:
                with self.subTest(user=user.username, page=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('receipt', args=[order.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('store_detail', args=[self.store.id])).status_code, 200)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(reverse('manage_store', args=[self.store.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('delete_store', args=[self.store.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('upload_pickup_proof', args=[order.id])).status_code, 200)


class LoginThrottleTests(FlowTestCase):
    def test_locks_after_repeated_failures(self):
        for _ in range(5):
            self.client.post(reverse('login'), {'username': 'buyer', 'password': 'wrong'})
        resp = self.client.post(reverse('login'), {'username': 'buyer', 'password': 'pw-12345678!'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_open_redirect_is_ignored(self):
        resp = self.client.post(reverse('login'), {
            'username': 'buyer', 'password': 'pw-12345678!', 'next': 'https://evil.example/',
        })
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)

    def test_local_next_is_followed(self):
        resp = self.client.post(reverse('login'), {
            'username': 'buyer', 'password': 'pw-12345678!', 'next': '/my-orders/',
        })
        self.assertRedirects(resp, '/my-orders/', fetch_redirect_response=False)


class UploadValidationTests(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.order = Reservation.objects.create(user=self.buyer, store=self.store, tank=self.tank, name='Ana')
        self.client.force_login(self.seller)
        self.url = reverse('upload_pickup_proof', args=[self.order.id])

    def test_fake_image_is_rejected(self):
        fake = SimpleUploadedFile('proof.png', b'<?php echo 1; ?>', content_type='image/png')
        self.client.post(self.url, {'pickup_proof': fake})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

    def test_real_image_is_saved_under_random_name(self):
        photo = SimpleUploadedFile('juan dela cruz.png', png_bytes(), content_type='image/png')
        with self.temp_media():
            self.client.post(self.url, {'pickup_proof': photo})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_approval')
        self.assertRegex(self.order.pickup_proof.name, r'^pickup_proofs/[0-9a-f]{32}\.png$')


class ApplicationReviewTests(FlowTestCase):
    def test_approval_notifies_once_and_cannot_be_reversed_by_replay(self):
        applicant = User.objects.create_user('applicant', password='pw-12345678!')
        app = SellerApplication.objects.create(
            user=applicant, business_name='Gas Co', business_address='Somewhere',
            business_permit='seller_documents/permits/x.pdf', valid_id='seller_documents/ids/y.pdf',
            phone='09171234567', email='a@example.com',
        )
        self.client.force_login(self.admin)
        url = reverse('admin_review_application', args=[app.id])
        self.client.post(url, {'decision': 'approved'})
        applicant.profile.refresh_from_db()
        self.assertTrue(applicant.profile.is_seller())
        self.assertEqual(Notification.objects.filter(user=applicant).count(), 1)

        self.client.post(url, {'decision': 'rejected', 'rejection_reason': 'changed my mind'})
        app.refresh_from_db()
        self.assertEqual(app.status, 'approved')


@override_settings(SECURE_SSL_REDIRECT=False)
class HeaderTests(TestCase):
    def test_security_headers_present(self):
        resp = self.client.get(reverse('login'))
        csp = resp.headers['Content-Security-Policy']
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertNotIn('unsafe-inline', csp)
        self.assertEqual(resp.headers['X-Frame-Options'], 'DENY')
        self.assertIn('geolocation=(self)', resp.headers['Permissions-Policy'])

    def test_allauth_login_redirects_to_site_login(self):
        resp = self.client.get('/accounts/login/?next=/map/')
        self.assertRedirects(resp, '/login/?next=/map/', fetch_redirect_response=False)
