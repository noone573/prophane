from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

# Extend User model with profile
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('seller', 'Seller'),
        ('admin', 'Admin'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved')
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
    def is_seller(self):
        return self.role == 'seller' and self.status == 'approved'
    
    def is_admin(self):
        return self.role == 'admin'
    
    def can_create_store(self):
        return self.is_seller() or self.is_admin()


# Seller Application for approval
class SellerApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_application')
    business_name = models.CharField(max_length=200)
    business_address = models.TextField()
    business_permit = models.FileField(upload_to='seller_documents/permits/')
    dti_certificate = models.FileField(upload_to='seller_documents/dti/', blank=True, null=True)
    mayors_permit = models.FileField(upload_to='seller_documents/mayors/', blank=True, null=True)
    valid_id = models.FileField(upload_to='seller_documents/ids/')
    tin_number = models.CharField(max_length=50, blank=True, null=True)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.business_name} - {self.user.username} ({self.status})"


class Store(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_stores")
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    description = models.TextField(default="Quality propane gas supplier")
    owner_photo = models.ImageField(upload_to='store_owners/', help_text="Upload your photo")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PropaneTank(models.Model):
    TANK_TYPES = [
        ('A/S Valve Gasul', 'A/S Valve Gasul'),
        ('POL Valve Gasul', 'POL Valve Gasul'),
        ('Price Gas', 'Price Gas'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="tanks")
    tank_type = models.CharField(max_length=50, choices=TANK_TYPES)
    stock = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('store', 'tank_type')

    def __str__(self):
        return f"{self.tank_type} - {self.store.name}"


class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Pickup'),
        ('pending_approval', 'Pending Admin Approval'),
        ('approved', 'Approved - Completed'),
        ('rejected', 'Pickup Proof Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    tank = models.ForeignKey(PropaneTank, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Pickup proof fields (uploaded by SELLER)
    pickup_proof = models.ImageField(upload_to='pickup_proofs/', null=True, blank=True)
    pickup_proof_uploaded_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reservations')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_notified = models.BooleanField(default=False)

    def can_upload_proof(self):
        """Seller can upload pickup proof when status is pending or rejected"""
        return self.status in ['pending', 'rejected']
    
    def needs_admin_review(self):
        return self.status == 'pending_approval'

    def __str__(self):
        return f"Reservation {self.id} by {self.user.username}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.TextField()
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}"


# Signal to create user profile automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, role='customer')


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


# Signal to notify store owner when a reservation is made
@receiver(post_save, sender=Reservation)
def notify_store_owner(sender, instance, created, **kwargs):
    if created and not instance.is_notified:
        Notification.objects.create(
            user=instance.store.owner,
            message=f"🛒 New order #{instance.id}! {instance.name} purchased {instance.tank.tank_type} from {instance.store.name}. Please confirm pickup and upload proof.",
            reservation=instance
        )
        instance.is_notified = True
        instance.save()


# Signal to notify user when seller application status changes
@receiver(post_save, sender=SellerApplication)
def notify_application_status(sender, instance, created, **kwargs):
    if not created and instance.status in ['approved', 'rejected']:
        if instance.status == 'approved':
            # Update user profile to seller
            profile = instance.user.profile
            profile.role = 'seller'
            profile.status = 'approved'
            profile.save()
            
            message = f"Congratulations! Your seller application for '{instance.business_name}' has been APPROVED. You can now create stores!"
        else:
            message = f"Your seller application for '{instance.business_name}' has been rejected. Reason: {instance.rejection_reason}"
        
        Notification.objects.create(
            user=instance.user,
            message=message
        )