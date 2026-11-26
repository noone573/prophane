from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import throttle
from .decorators import admin_required, seller_required
from .forms import MAX_PRICE, MAX_STOCK, SellerApplicationForm, SignupForm, StoreCreationForm
from .models import (
    Notification, PropaneTank, Reservation, SellerApplication, Store, UserProfile,
)
from .validators import validate_image_upload

MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'

MAX_QTY_PER_ORDER = 5
MAX_OPEN_ORDERS = 3
MAX_REASON_LENGTH = 500

ORDER_STATUSES = {key for key, _ in Reservation.STATUS_CHOICES}
APPLICATION_STATUSES = {key for key, _ in SellerApplication.STATUS_CHOICES}


def _safe_next(request):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return None


# Accounts

def home(request):
    return redirect('dashboard' if request.user.is_authenticated else 'login')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend=MODEL_BACKEND)
        messages.success(request, f'Welcome to Propane Point, {user.username}.')
        return redirect('dashboard')
    return render(request, 'signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        username = request.POST.get('username', '')
        if throttle.is_locked(request, username):
            form = AuthenticationForm(request)
            messages.error(request, 'Too many failed sign-in attempts. Please wait 15 minutes and try again.')
        elif form.is_valid():
            user = form.get_user()
            throttle.reset(request, username)
            login(request, user, backend=MODEL_BACKEND)
            return redirect(_safe_next(request) or 'dashboard')
        else:
            throttle.record_failure(request, username)

    return render(request, 'login.html', {'form': form, 'next': _safe_next(request) or ''})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('login')


@login_required
def dashboard(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.role == 'admin':
        return redirect('admin_dashboard')
    if profile.role == 'seller':
        return redirect('my_stores' if profile.status == 'approved' else 'seller_pending')
    return redirect('map')


# Customers

@login_required
def map(request):
    stores = (
        Store.objects.filter(is_active=True)
        .select_related('owner')
        .prefetch_related(Prefetch('tanks', queryset=PropaneTank.objects.filter(is_active=True)))
    )
    default_photo = static('img/default.png')
    tank_image = static('img/11kg.png')
    stores_data = [
        {
            'id': store.id,
            'name': store.name,
            'lat': store.latitude,
            'lng': store.longitude,
            'description': store.description,
            'owner': store.owner.get_full_name() or store.owner.username,
            'photo': store.owner_photo.url if store.owner_photo else default_photo,
            'tanks': [
                {
                    'id': tank.id,
                    'type': tank.tank_type,
                    'price': str(tank.price),
                    'stock': tank.stock,
                    'image': tank_image,
                }
                for tank in store.tanks.all()
            ],
        }
        for store in stores
    ]
    return render(request, 'customer/map.html', {
        'stores_data': stores_data,
        'store_count': len(stores_data),
        'max_qty': MAX_QTY_PER_ORDER,
    })


@login_required
def store_detail(request, store_id):
    store = get_object_or_404(Store.objects.select_related('owner'), id=store_id, is_active=True)
    tanks = store.tanks.filter(is_active=True, stock__gt=0)
    return render(request, 'customer/store_detail.html', {
        'store': store,
        'tanks': tanks,
        'max_qty': MAX_QTY_PER_ORDER,
    })


@login_required
@require_POST
def reserve_tank(request, tank_id):
    name = ' '.join(request.POST.get('name', '').split())[:100]
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 0

    tank = get_object_or_404(PropaneTank.objects.select_related('store'), id=tank_id)
    back = redirect('store_detail', store_id=tank.store_id)

    if not name:
        messages.error(request, 'Please enter the name of the person picking up the order.')
        return back
    if not 1 <= quantity <= MAX_QTY_PER_ORDER:
        messages.error(request, f'You can reserve 1 to {MAX_QTY_PER_ORDER} tanks per order.')
        return back
    if tank.store.owner_id == request.user.id:
        messages.error(request, "You can't reserve tanks from your own store.")
        return back

    open_orders = Reservation.objects.filter(
        user=request.user, status__in=['pending', 'pending_approval', 'rejected']
    ).count()
    if open_orders >= MAX_OPEN_ORDERS:
        messages.error(
            request,
            f'You already have {open_orders} open orders. Pick them up or cancel one before reserving more.',
        )
        return redirect('my_orders')

    with transaction.atomic():
        # Lock the row so two customers can't both take the last tank
        tank = PropaneTank.objects.select_for_update().select_related('store').get(id=tank_id)
        if not (tank.is_active and tank.store.is_active):
            messages.error(request, 'This tank is no longer available.')
            return redirect('map')
        if tank.stock < quantity:
            messages.error(request, f'Only {tank.stock} left in stock.' if tank.stock else 'This tank is out of stock.')
            return back

        tank.stock -= quantity
        tank.save(update_fields=['stock'])
        reservation = Reservation.objects.create(
            user=request.user,
            store=tank.store,
            tank=tank,
            name=name,
            quantity=quantity,
            unit_price=tank.price,
            status='pending',
        )

    return redirect('receipt', reservation_id=reservation.id)


@login_required
def receipt(request, reservation_id):
    reservation = get_object_or_404(
        Reservation.objects.select_related('store', 'tank'), id=reservation_id, user=request.user
    )
    return render(request, 'receipt.html', {'reservation': reservation})


@login_required
def my_orders(request):
    orders = (
        Reservation.objects.filter(user=request.user)
        .select_related('store', 'tank')
        .order_by('-created_at')
    )
    return render(request, 'customer/my_orders.html', {'orders': orders})


@login_required
@require_POST
def cancel_order(request, reservation_id):
    with transaction.atomic():
        reservation = get_object_or_404(
            Reservation.objects.select_for_update(), id=reservation_id, user=request.user
        )
        if reservation.status != 'pending':
            messages.error(request, 'Only orders that have not been picked up can be cancelled.')
            return redirect('my_orders')

        reservation.status = 'cancelled'
        reservation.save(update_fields=['status'])
        PropaneTank.objects.filter(id=reservation.tank_id).update(stock=F('stock') + reservation.quantity)

    Notification.objects.create(
        user=reservation.store.owner,
        message=f'Order #{reservation.id} was cancelled by the customer.',
        reservation=reservation,
    )
    messages.success(request, f'Order #{reservation.id} cancelled.')
    return redirect('my_orders')


@login_required
def notifications(request):
    items = list(
        Notification.objects.filter(user=request.user)
        .select_related('reservation__store')
        .order_by('-created_at')[:100]
    )
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, 'notifications.html', {'notifications': items, 'unread_count': 0})


# Seller applications

@login_required
def apply_seller(request):
    profile = request.user.profile
    if profile.role == 'seller':
        return redirect('my_stores' if profile.status == 'approved' else 'seller_pending')
    if profile.role == 'admin':
        messages.info(request, 'Administrators do not need a seller application.')
        return redirect('dashboard')

    existing = SellerApplication.objects.filter(user=request.user).first()
    if existing and existing.status == 'pending':
        return redirect('seller_pending')

    if request.method == 'POST':
        # A rejected applicant re-applies by updating their previous record
        form = SellerApplicationForm(request.POST, request.FILES, instance=existing)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.status = 'pending'
            application.rejection_reason = None
            application.reviewed_by = None
            application.reviewed_at = None
            application.save()
            messages.success(request, 'Application submitted. Reviews usually take 2 to 3 business days.')
            return redirect('seller_pending')
    else:
        form = SellerApplicationForm(instance=existing)

    return render(request, 'seller/apply.html', {'form': form, 'previous': existing})


@login_required
def seller_pending(request):
    application = SellerApplication.objects.filter(user=request.user).first()
    if application is None:
        return redirect('apply_seller')
    if application.status == 'approved' and request.user.profile.is_seller():
        return redirect('my_stores')
    return render(request, 'seller/pending.html', {'application': application})


# Seller portal

@seller_required
def my_stores(request):
    stores = (
        Store.objects.filter(owner=request.user)
        .prefetch_related('tanks')
        .annotate(open_orders=Count('reservation', filter=Q(reservation__status__in=['pending', 'rejected'])))
        .order_by('-created_at')
    )
    return render(request, 'seller/my_stores.html', {'stores': stores})


@seller_required
def create_store(request):
    if request.method == 'POST':
        form = StoreCreationForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                store = form.save(commit=False)
                store.owner = request.user
                store.save()
                PropaneTank.objects.bulk_create([
                    PropaneTank(store=store, tank_type=t, price=price, stock=stock, is_active=True)
                    for t, price, stock in form.tank_rows()
                ])
            messages.success(request, f'"{store.name}" is now live on the map.')
            return redirect('my_stores')
    else:
        form = StoreCreationForm()

    return render(request, 'seller/create_store.html', {'form': form})


@seller_required
def manage_store(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    tanks = list(store.tanks.all().order_by('tank_type'))

    if request.method == 'POST':
        errors = []
        updates = []
        for tank in tanks:
            try:
                stock = int(request.POST.get(f'stock_{tank.id}', ''))
                price = Decimal(request.POST.get(f'price_{tank.id}', '')).quantize(Decimal('0.01'))
            except (ValueError, InvalidOperation):
                errors.append(f'{tank.tank_type}: enter a valid price and stock.')
                continue
            if not 0 <= stock <= MAX_STOCK:
                errors.append(f'{tank.tank_type}: stock must be between 0 and {MAX_STOCK}.')
                continue
            if not Decimal('1') <= price <= MAX_PRICE:
                errors.append(f'{tank.tank_type}: price must be between ₱1 and ₱{MAX_PRICE:,.0f}.')
                continue
            tank.stock = stock
            tank.price = price
            tank.is_active = request.POST.get(f'active_{tank.id}') == 'on'
            updates.append(tank)

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            PropaneTank.objects.bulk_update(updates, ['stock', 'price', 'is_active'])
            messages.success(request, 'Inventory saved.')
        return redirect('manage_store', store_id=store.id)

    pending_orders = (
        Reservation.objects.filter(store=store, status__in=['pending', 'rejected', 'pending_approval'])
        .select_related('tank', 'user')
        .order_by('-created_at')
    )
    return render(request, 'seller/manage_store.html', {
        'store': store,
        'tanks': tanks,
        'pending_orders': pending_orders,
        'max_stock': MAX_STOCK,
        'max_price': MAX_PRICE,
    })


@seller_required
def delete_store(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    open_orders = Reservation.objects.filter(
        store=store, status__in=['pending', 'pending_approval', 'rejected']
    ).count()

    if request.method == 'POST':
        if open_orders:
            messages.error(request, 'This store still has open orders. Complete or cancel them first.')
            return redirect('manage_store', store_id=store.id)
        name = store.name
        store.delete()
        messages.success(request, f'"{name}" was deleted.')
        return redirect('my_stores')

    return render(request, 'seller/confirm_delete_store.html', {'store': store, 'open_orders': open_orders})


@seller_required
def upload_pickup_proof(request, reservation_id):
    reservation = get_object_or_404(
        Reservation.objects.select_related('store', 'tank', 'user'),
        id=reservation_id,
        store__owner=request.user,
    )
    if not reservation.can_upload_proof():
        messages.error(request, 'A pickup photo cannot be uploaded for this order.')
        return redirect('manage_store', store_id=reservation.store_id)

    if request.method == 'POST':
        photo = request.FILES.get('pickup_proof')
        if not photo:
            messages.error(request, 'Choose a photo to upload.')
            return redirect('upload_pickup_proof', reservation_id=reservation.id)
        try:
            validate_image_upload(photo)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return redirect('upload_pickup_proof', reservation_id=reservation.id)

        reservation.pickup_proof = photo
        reservation.pickup_proof_uploaded_at = timezone.now()
        reservation.status = 'pending_approval'
        reservation.rejection_reason = None
        reservation.save()

        Notification.objects.create(
            user=reservation.user,
            message=f'The seller confirmed pickup for order #{reservation.id}. It is now waiting for admin verification.',
            reservation=reservation,
        )
        messages.success(request, 'Pickup photo uploaded. An admin will verify it shortly.')
        return redirect('manage_store', store_id=reservation.store_id)

    return render(request, 'seller/upload.html', {'reservation': reservation})


# Admin portal

@admin_required
def admin_dashboard(request):
    return render(request, 'admin/dashboard.html', {
        'pending_applications': SellerApplication.objects.filter(status='pending').count(),
        'total_sellers': UserProfile.objects.filter(role='seller', status='approved').count(),
        'total_stores': Store.objects.filter(is_active=True).count(),
        'total_customers': UserProfile.objects.filter(role='customer').count(),
        'pending_review_count': Reservation.objects.filter(status='pending_approval').count(),
        'recent_applications': SellerApplication.objects.select_related('user').order_by('-created_at')[:5],
    })


@admin_required
def admin_applications(request):
    status_filter = request.GET.get('status', 'all')
    if status_filter not in APPLICATION_STATUSES:
        status_filter = 'all'

    applications = SellerApplication.objects.select_related('user').order_by('-created_at')
    if status_filter != 'all':
        applications = applications.filter(status=status_filter)

    counts = dict(
        SellerApplication.objects.values_list('status').annotate(n=Count('id')).values_list('status', 'n')
    )
    return render(request, 'admin/applications.html', {
        'applications': applications,
        'status_filter': status_filter,
        'pending_count': counts.get('pending', 0),
        'approved_count': counts.get('approved', 0),
        'rejected_count': counts.get('rejected', 0),
    })


@admin_required
def admin_review_application(request, application_id):
    application = get_object_or_404(SellerApplication.objects.select_related('user'), id=application_id)

    if request.method == 'POST':
        if application.status != 'pending':
            messages.error(request, 'This application has already been reviewed.')
            return redirect('admin_applications')

        decision = request.POST.get('decision')
        reason = request.POST.get('rejection_reason', '').strip()[:MAX_REASON_LENGTH]

        if decision == 'approved':
            with transaction.atomic():
                application.status = 'approved'
                application.rejection_reason = None
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.save()
                UserProfile.objects.filter(user=application.user).update(role='seller', status='approved')
            Notification.objects.create(
                user=application.user,
                message=f'Your seller application for "{application.business_name}" was approved. You can now create a store.',
            )
            messages.success(request, f'{application.user.username} is now a seller.')
            return redirect('admin_applications')

        if decision == 'rejected':
            if not reason:
                messages.error(request, 'Add a reason so the applicant knows what to fix.')
                return render(request, 'admin/review_application.html', {'application': application})
            application.status = 'rejected'
            application.rejection_reason = reason
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
            Notification.objects.create(
                user=application.user,
                message=f'Your seller application for "{application.business_name}" was not approved. Reason: {reason}',
            )
            messages.info(request, 'Application rejected and the applicant was notified.')
            return redirect('admin_applications')

        messages.error(request, 'Choose approve or reject.')

    return render(request, 'admin/review_application.html', {'application': application})


@admin_required
def admin_sellers(request):
    sellers = (
        UserProfile.objects.filter(role='seller', status__in=['approved', 'suspended'])
        .select_related('user')
        .prefetch_related('user__owned_stores')
        .order_by('user__username')
    )
    return render(request, 'admin/sellers.html', {'sellers': sellers})


@admin_required
@require_POST
def admin_suspend_seller(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    if profile.role != 'seller':
        messages.error(request, 'That account is not a seller.')
        return redirect('admin_sellers')

    if profile.status == 'approved':
        profile.status = 'suspended'
        profile.save(update_fields=['status', 'updated_at'])
        Store.objects.filter(owner=user).update(is_active=False)
        Notification.objects.create(
            user=user,
            message='Your seller account has been suspended and your stores are hidden from the map. Contact support for details.',
        )
        messages.info(request, f'{user.username} was suspended and their stores were hidden.')
    else:
        profile.status = 'approved'
        profile.save(update_fields=['status', 'updated_at'])
        Notification.objects.create(
            user=user,
            message='Your seller account was reactivated. Turn your stores back on from the admin team or contact support.',
        )
        messages.success(request, f'{user.username} was reactivated.')
    return redirect('admin_sellers')


@admin_required
def admin_stores(request):
    stores = (
        Store.objects.select_related('owner')
        .annotate(tank_count=Count('tanks'))
        .order_by('-created_at')
    )
    return render(request, 'admin/stores.html', {'stores': stores})


@admin_required
@require_POST
def admin_toggle_store(request, store_id):
    store = get_object_or_404(Store, id=store_id)
    store.is_active = not store.is_active
    store.save(update_fields=['is_active'])
    messages.success(request, f'"{store.name}" is now {"visible" if store.is_active else "hidden"}.')
    return redirect('admin_stores')


@admin_required
def admin_orders(request):
    status_filter = request.GET.get('status', 'all')
    if status_filter not in ORDER_STATUSES:
        status_filter = 'all'

    orders = (
        Reservation.objects.select_related('user', 'store', 'store__owner', 'tank', 'reviewed_by')
        .order_by('-created_at')
    )
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)

    return render(request, 'admin/orders.html', {
        'orders': orders[:200],
        'status_filter': status_filter,
        'status_choices': Reservation.STATUS_CHOICES,
        'pending_review_count': Reservation.objects.filter(status='pending_approval').count(),
    })


@admin_required
def admin_review_pickup(request, reservation_id):
    reservation = get_object_or_404(
        Reservation.objects.select_related('user', 'store', 'store__owner', 'tank'), id=reservation_id
    )
    if reservation.status != 'pending_approval':
        messages.error(request, 'This order is not waiting for review.')
        return redirect('admin_orders')

    if request.method == 'POST':
        decision = request.POST.get('decision')
        reason = request.POST.get('rejection_reason', '').strip()[:MAX_REASON_LENGTH]

        if decision == 'approved':
            reservation.status = 'approved'
            reservation.reviewed_by = request.user
            reservation.reviewed_at = timezone.now()
            reservation.save()
            Notification.objects.bulk_create([
                Notification(user=reservation.user, reservation=reservation,
                             message=f'Order #{reservation.id} is complete. Thanks for using Propane Point.'),
                Notification(user=reservation.store.owner, reservation=reservation,
                             message=f'Pickup for order #{reservation.id} was verified.'),
            ])
            messages.success(request, f'Order #{reservation.id} marked complete.')
            return redirect('admin_orders')

        if decision == 'rejected':
            if not reason:
                messages.error(request, 'Add a reason so the seller knows what to fix.')
                return render(request, 'admin/review_pickup.html', {'reservation': reservation})
            # Stock stays reserved: the seller is expected to upload a better photo.
            reservation.status = 'rejected'
            reservation.rejection_reason = reason
            reservation.reviewed_by = request.user
            reservation.reviewed_at = timezone.now()
            reservation.save()
            Notification.objects.bulk_create([
                Notification(user=reservation.store.owner, reservation=reservation,
                             message=f'The pickup photo for order #{reservation.id} was rejected: {reason}. Please upload a new one.'),
                Notification(user=reservation.user, reservation=reservation,
                             message=f'The pickup photo for order #{reservation.id} needs to be re-submitted by the seller.'),
            ])
            messages.info(request, 'Pickup photo rejected. Seller and customer were notified.')
            return redirect('admin_orders')

        messages.error(request, 'Choose approve or reject.')

    return render(request, 'admin/review_pickup.html', {'reservation': reservation})
