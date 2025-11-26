from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta
from .models import Store, PropaneTank, Reservation, Notification, SellerApplication, UserProfile
from .forms import StoreCreationForm, SellerApplicationForm, ApplicationReviewForm
from .decorators import seller_required, admin_required, customer_only


# ==================== AUTHENTICATION ====================
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
        
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"Welcome to Propane Point, {user.username}! 🎉")
            return redirect("dashboard")
        
    else:
        form = UserCreationForm()
    return render(request, "signup.html", {"form": form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
        
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"Welcome back, {user.username}! 👋")
            return redirect("dashboard")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})

@login_required
def logout_view(request):
    username = request.user.username
    logout(request)
    messages.success(request, f"Goodbye, {username}! 👋")
    return redirect("login")


# ==================== DASHBOARD (ROLE-BASED ROUTING) ====================
@login_required
def dashboard(request):
    """Main dashboard that routes based on user role"""
    profile = request.user.profile
    
    if profile.role == 'admin':
        return redirect('admin_dashboard')
    elif profile.role == 'seller':
        if profile.status == 'approved':
            return redirect('my_stores')
        else:
            return redirect('seller_pending')
    else:  # customer
        return redirect('map')


# ==================== CUSTOMER PORTAL ====================
@login_required
def map(request):
    """Customer view - Browse and buy (HOMEPAGE)"""
    stores = Store.objects.filter(is_active=True)
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return render(request, "customer/map.html", {
        "stores": stores,
        "unread_count": unread_count
    })

@login_required
def store_detail(request, store_id):
    """Customer views store details and available tanks"""
    store = get_object_or_404(Store, id=store_id, is_active=True)
    tanks = store.tanks.filter(is_active=True, stock__gt=0)
    
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return render(request, "customer/store_detail.html", {
        "store": store,
        "tanks": tanks,
        "unread_count": unread_count
    })

@login_required
def reserve_tank(request, tank_id):
    """Customer reserves a tank"""
    tank = get_object_or_404(PropaneTank, id=tank_id)
    
    if tank.stock <= 0:
        messages.error(request, "This tank is out of stock.")
        return redirect("map")
    
    if request.method == "POST":
        name = request.POST.get('name', '').strip()
        
        if not name:
            messages.error(request, "Please provide your name.")
            return redirect("store_detail", store_id=tank.store.id)
        
        # Create reservation with 'pending' status
        reservation = Reservation.objects.create(
            user=request.user,
            store=tank.store,
            tank=tank,
            name=name,
            status='pending'
        )
        
        # Reduce stock
        tank.stock -= 1
        tank.save()
        
        messages.success(request, "Reservation created! The seller will confirm pickup and upload proof.")
        return redirect("receipt", reservation_id=reservation.id)
    
    return redirect("store_detail", store_id=tank.store.id)

@login_required
def receipt(request, reservation_id):
    """Show receipt for reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    return render(request, "receipt.html", {"reservation": reservation})

@login_required
def my_orders(request):
    """Customer orders"""
    orders = Reservation.objects.filter(user=request.user).order_by('-created_at')
    
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, "customer/my_orders.html", {
        "orders": orders,
        "unread_count": unread_count
    })

@login_required
def cancel_order(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    
    if reservation.status == 'pending':
        reservation.status = 'cancelled'
        reservation.tank.stock += 1
        reservation.tank.save()
        reservation.save()
        
        # Notify seller
        Notification.objects.create(
            user=reservation.store.owner,
            message=f"❌ Order #{reservation.id} was cancelled by the customer."
        )
        
        messages.success(request, "Order cancelled successfully.")
    else:
        messages.error(request, "Cannot cancel this order.")
    
    return redirect("my_orders")

@login_required
def notifications(request):
    """View all notifications"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Mark all as read
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    unread_count = 0
    
    return render(request, "notifications.html", {
        "notifications": notifications,
        "unread_count": unread_count
    })


# ==================== SELLER APPLICATION ====================
@login_required
def apply_seller(request):
    """Apply to become a seller"""
    profile = request.user.profile
    
    # Check if already a seller
    if profile.role == 'seller':
        messages.info(request, "You are already a seller!")
        return redirect("my_stores")
    
    # Check if application exists
    if hasattr(request.user, 'seller_application'):
        application = request.user.seller_application
        if application.status == 'pending':
            messages.info(request, "Your application is still pending review.")
            return redirect("seller_pending")
        elif application.status == 'rejected':
            messages.warning(request, "Your previous application was rejected. You can apply again.")
    
    if request.method == "POST":
        form = SellerApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.status = 'pending'
            application.save()
            
            messages.success(request, "Application submitted! We'll review it within 2-3 business days.")
            return redirect("seller_pending")
    else:
        form = SellerApplicationForm()
    
    return render(request, "seller/apply.html", {"form": form})

@login_required
def seller_pending(request):
    """Pending seller application view"""
    try:
        application = request.user.seller_application
    except:
        messages.error(request, "No application found.")
        return redirect("apply_seller")
    
    return render(request, "seller/pending.html", {"application": application})


# ==================== SELLER PORTAL ====================
@seller_required
def my_stores(request):
    """Seller views their stores"""
    stores = Store.objects.filter(owner=request.user).order_by('-created_at')
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return render(request, "seller/my_stores.html", {
        "stores": stores,
        "unread_count": unread_count
    })

@seller_required
def create_store(request):
    if request.method == "POST":
        form = StoreCreationForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            store.save()
            
            tanks_to_sell = form.cleaned_data['tanks_to_sell']
            
            for tank_type in tanks_to_sell:
                if tank_type == 'A/S Valve Gasul':
                    price = form.cleaned_data['as_valve_price']
                    stock = form.cleaned_data['as_valve_stock']
                elif tank_type == 'POL Valve Gasul':
                    price = form.cleaned_data['pol_valve_price']
                    stock = form.cleaned_data['pol_valve_stock']
                elif tank_type == 'Price Gas':
                    price = form.cleaned_data['price_gas_price']
                    stock = form.cleaned_data['price_gas_stock']
                
                PropaneTank.objects.create(
                    store=store,
                    tank_type=tank_type,
                    price=price,
                    stock=stock,
                    is_active=True
                )
            
            messages.success(request, f"Store '{store.name}' created successfully!")
            return redirect("my_stores")
    else:
        form = StoreCreationForm()
    
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, "seller/create_store.html", {
        "form": form,
        "unread_count": unread_count
    })

@seller_required
def manage_store(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    tanks = store.tanks.all()
    
    if request.method == "POST":
        for tank in tanks:
            stock = request.POST.get(f"stock_{tank.id}")
            price = request.POST.get(f"price_{tank.id}")
            is_active = request.POST.get(f"active_{tank.id}") == "on"
            
            if stock and price:
                tank.stock = int(stock)
                tank.price = float(price)
                tank.is_active = is_active
                tank.save()
        
        messages.success(request, "Store updated successfully!")
        return redirect("manage_store", store_id=store_id)
    
    # Get orders that need pickup proof upload or are pending approval
    pending_orders = Reservation.objects.filter(
        store=store,
        status__in=['pending', 'rejected', 'pending_approval']
    ).order_by('-created_at')
    
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, "seller/manage_store.html", {
        "store": store,
        "tanks": tanks,
        "pending_orders": pending_orders,
        "unread_count": unread_count
    })

@seller_required
def delete_store(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    
    if request.method == "POST":
        store_name = store.name
        store.delete()
        messages.success(request, f"Store '{store_name}' deleted.")
        return redirect("my_stores")
    
    return render(request, "comfirm_delete_store.html", {"store": store})


# ==================== SELLER - Upload Pickup Proof ====================
@seller_required
def upload_pickup_proof(request, reservation_id):
    """Seller uploads proof that customer picked up their order"""
    reservation = get_object_or_404(
        Reservation, 
        id=reservation_id, 
        store__owner=request.user
    )
    
    # Check if seller can upload proof
    if not reservation.can_upload_proof():
        messages.error(request, "Cannot upload proof for this order.")
        return redirect("manage_store", store_id=reservation.store.id)
    
    if request.method == "POST":
        pickup_proof = request.FILES.get('pickup_proof')
        
        if not pickup_proof:
            messages.error(request, "Please select an image to upload.")
            return redirect("upload_pickup_proof", reservation_id=reservation_id)
        
        # Validate file type
        valid_extensions = ['jpg', 'jpeg', 'png']
        file_extension = pickup_proof.name.split('.')[-1].lower()
        if file_extension not in valid_extensions:
            messages.error(request, "Only JPG, JPEG, and PNG files are allowed.")
            return redirect("upload_pickup_proof", reservation_id=reservation_id)
        
        # Validate file size (5MB)
        if pickup_proof.size > 5 * 1024 * 1024:
            messages.error(request, "File size must be less than 5MB.")
            return redirect("upload_pickup_proof", reservation_id=reservation_id)
        
        # Save the pickup proof
        reservation.pickup_proof = pickup_proof
        reservation.pickup_proof_uploaded_at = timezone.now()
        reservation.status = 'pending_approval'
        reservation.save()
        
        # Notify customer
        Notification.objects.create(
            user=reservation.user,
            message=f"📸 Seller has uploaded pickup proof for your order #{reservation.id}. Waiting for admin approval.",
            reservation=reservation
        )
        
        messages.success(request, "Pickup proof uploaded successfully! Waiting for admin approval.")
        return redirect("manage_store", store_id=reservation.store.id)
    
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, "seller/upload.html", {
        "reservation": reservation,
        "unread_count": unread_count
    })


# ==================== ADMIN PORTAL ====================
@admin_required
def admin_dashboard(request):
    """Admin dashboard"""
    pending_applications = SellerApplication.objects.filter(status='pending').count()
    total_sellers = UserProfile.objects.filter(role='seller', status='approved').count()
    total_stores = Store.objects.count()
    total_customers = UserProfile.objects.filter(role='customer').count()
    pending_review_count = Reservation.objects.filter(status='pending_approval').count()
    
    recent_applications = SellerApplication.objects.order_by('-created_at')[:5]
    
    return render(request, "admin/dashboard.html", {
        "pending_applications": pending_applications,
        "total_sellers": total_sellers,
        "total_stores": total_stores,
        "total_customers": total_customers,
        "pending_review_count": pending_review_count,
        "recent_applications": recent_applications
    })

@admin_required
def admin_review_application(request, application_id):
    """Admin reviews and approves/rejects seller application"""
    application = get_object_or_404(SellerApplication, id=application_id)
    
    if request.method == "POST":
        decision = request.POST.get('decision')
        rejection_reason = request.POST.get('rejection_reason', '')
        
        if decision == 'approved':
            application.status = 'approved'
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
            
            # Update user profile to seller
            profile = application.user.profile
            profile.role = 'seller'
            profile.status = 'approved'
            profile.save()
            
            # Send notification
            Notification.objects.create(
                user=application.user,
                message=f"🎉 Congratulations! Your seller application for '{application.business_name}' has been APPROVED! You can now create stores and start selling."
            )
            
            messages.success(request, f"Application approved! {application.user.username} is now a seller.")
            return redirect('admin_applications')
            
        elif decision == 'rejected':
            if not rejection_reason:
                messages.error(request, "Please provide a rejection reason.")
                return render(request, "admin/review_application.html", {"application": application})
            
            application.status = 'rejected'
            application.rejection_reason = rejection_reason
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
            
            # Send notification
            Notification.objects.create(
                user=application.user,
                message=f"❌ Your seller application for '{application.business_name}' has been rejected. Reason: {rejection_reason}"
            )
            
            messages.warning(request, "Application rejected and applicant notified.")
            return redirect('admin_applications')
    
    return render(request, "admin/review_application.html", {"application": application})

@admin_required
def admin_applications(request):
    """List all seller applications"""
    status_filter = request.GET.get('status', 'all')
    
    if status_filter == 'all':
        applications = SellerApplication.objects.all().order_by('-created_at')
    else:
        applications = SellerApplication.objects.filter(status=status_filter).order_by('-created_at')
    
    pending_count = SellerApplication.objects.filter(status='pending').count()
    approved_count = SellerApplication.objects.filter(status='approved').count()
    rejected_count = SellerApplication.objects.filter(status='rejected').count()
    
    return render(request, "admin/applications.html", {
        "applications": applications,
        "status_filter": status_filter,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count
    })

@admin_required
def admin_sellers(request):
    """Manage all sellers"""
    sellers = UserProfile.objects.filter(role='seller', status='approved')
    
    context = {
        "sellers": sellers
    }
    return render(request, "admin/sellers.html", context)

@admin_required
def admin_stores(request):
    """View and manage all stores"""
    stores = Store.objects.all().order_by('-created_at')
    
    return render(request, "admin/stores.html", {"stores": stores})

@admin_required
def admin_toggle_store(request, store_id):
    """Activate/deactivate a store"""
    store = get_object_or_404(Store, id=store_id)
    store.is_active = not store.is_active
    store.save()
    
    status = "activated" if store.is_active else "deactivated"
    messages.success(request, f"Store '{store.name}' has been {status}.")
    
    return redirect('admin_stores')

@admin_required
def admin_suspend_seller(request, user_id):
    """Suspend a seller account"""
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    
    if profile.role == 'seller':
        if profile.status == 'approved':
            profile.status = 'suspended'
            profile.save()
            
            # Deactivate all stores
            Store.objects.filter(owner=user).update(is_active=False)
            
            Notification.objects.create(
                user=user,
                message="⚠️ Your seller account has been suspended. Please contact support for more information."
            )
            
            messages.warning(request, f"Seller {user.username} has been suspended.")
        else:
            profile.status = 'approved'
            profile.save()
            
            messages.success(request, f"Seller {user.username} has been reactivated.")
    
    return redirect('admin_sellers')


# ==================== ADMIN - Review Pickup Proof ====================
@admin_required
def admin_review_pickup(request, reservation_id):
    """Admin reviews pickup proof submitted by seller"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    if reservation.status != 'pending_approval':
        messages.error(request, "This order is not pending review.")
        return redirect('admin_orders')
    
    if request.method == "POST":
        decision = request.POST.get('decision')
        rejection_reason = request.POST.get('rejection_reason', '')
        
        if decision == 'approved':
            reservation.status = 'approved'
            reservation.reviewed_by = request.user
            reservation.reviewed_at = timezone.now()
            reservation.save()
            
            # Notify customer
            Notification.objects.create(
                user=reservation.user,
                message=f"✅ Your order #{reservation.id} has been approved! The pickup is confirmed."
            )
            
            # Notify seller
            Notification.objects.create(
                user=reservation.store.owner,
                message=f"✅ Pickup proof for order #{reservation.id} has been approved by admin."
            )
            
            messages.success(request, "Pickup proof approved!")
            return redirect('admin_orders')
            
        elif decision == 'rejected':
            if not rejection_reason:
                messages.error(request, "Please provide a rejection reason.")
                return render(request, "admin/review_pickup.html", {"reservation": reservation})
            
            reservation.status = 'rejected'
            reservation.rejection_reason = rejection_reason
            reservation.reviewed_by = request.user
            reservation.reviewed_at = timezone.now()
            reservation.save()
            
            # Return stock
            reservation.tank.stock += 1
            reservation.tank.save()
            
            # Notify seller
            Notification.objects.create(
                user=reservation.store.owner,
                message=f"❌ Pickup proof for order #{reservation.id} was rejected. Reason: {rejection_reason}. Please upload a new proof."
            )
            
            # Notify customer
            Notification.objects.create(
                user=reservation.user,
                message=f"❌ Pickup proof for your order #{reservation.id} was rejected. The seller will need to resubmit."
            )
            
            messages.warning(request, "Pickup proof rejected. Seller and customer notified.")
            return redirect('admin_orders')
    
    return render(request, "admin/review_pickup.html", {"reservation": reservation})


@admin_required
def admin_orders(request):
    """View all orders/reservations"""
    status_filter = request.GET.get('status', 'all')
    
    if status_filter == 'all':
        orders = Reservation.objects.all().order_by('-created_at')
    else:
        orders = Reservation.objects.filter(status=status_filter).order_by('-created_at')
    
    pending_review_count = Reservation.objects.filter(status='pending_approval').count()
    
    return render(request, "admin/orders.html", {
        "orders": orders,
        "status_filter": status_filter,
        "pending_review_count": pending_review_count
    })
