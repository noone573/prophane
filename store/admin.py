from django.contrib import admin
from .models import Store, PropaneTank, Reservation, Notification


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'latitude', 'longitude', 'tank_count', 'created_at')
    search_fields = ('name', 'owner__username')
    list_filter = ('created_at', 'owner')
    list_per_page = 20
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Store Information', {
            'fields': ('owner', 'name', 'description')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def tank_count(self, obj):
        return obj.tanks.count()
    tank_count.short_description = 'Number of Tanks'


@admin.register(PropaneTank)
class PropaneTankAdmin(admin.ModelAdmin):
    list_display = ('tank_type', 'store', 'store_owner', 'price', 'stock', 'stock_status', 'is_active')
    list_filter = ('store', 'tank_type', 'is_active')
    search_fields = ('tank_type', 'store__name', 'store__owner__username')
    list_editable = ('stock', 'price', 'is_active')
    list_per_page = 20
    
    fieldsets = (
        ('Tank Information', {
            'fields': ('store', 'tank_type', 'is_active')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'stock'),
            'description': 'Manage tank pricing and stock levels'
        }),
    )
    
    def store_owner(self, obj):
        return obj.store.owner.username
    store_owner.short_description = 'Store Owner'
    
    def stock_status(self, obj):
        if obj.stock == 0:
            return '🔴 Out of Stock'
        elif obj.stock <= 5:
            return '🟡 Low Stock'
        elif obj.stock <= 10:
            return '🟠 Medium Stock'
        else:
            return '🟢 In Stock'
    stock_status.short_description = 'Stock Status'


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'store', 'store_owner', 'tank', 'created_at', 'total_price', 'is_notified')
    list_filter = ('store', 'created_at', 'tank__tank_type', 'is_notified')
    search_fields = ('user__username', 'name', 'store__name', 'store__owner__username')
    readonly_fields = ('user', 'store', 'tank', 'name', 'created_at', 'is_notified')
    date_hierarchy = 'created_at'
    list_per_page = 20
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('user', 'name')
        }),
        ('Reservation Details', {
            'fields': ('store', 'tank', 'created_at')
        }),
        ('Notification Status', {
            'fields': ('is_notified',)
        }),
    )
    
    def store_owner(self, obj):
        return obj.store.owner.username
    store_owner.short_description = 'Store Owner'
    
    def total_price(self, obj):
        return f'₱{obj.tank.price}'
    total_price.short_description = 'Price'
    
    def has_add_permission(self, request):
        # Prevent manual creation of reservations in admin
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete reservations
        return request.user.is_superuser


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'message_preview', 'reservation', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'message')
    readonly_fields = ('user', 'message', 'reservation', 'created_at')
    date_hierarchy = 'created_at'
    list_per_page = 20
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'message', 'reservation', 'is_read', 'created_at')
        }),
    )
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'
    
    def has_add_permission(self, request):
        # Notifications are created automatically
        return False


# Optional: Customize admin site header and title
admin.site.site_header = "Propane Point Administration"
admin.site.site_title = "Propane Point Admin"
admin.site.index_title = "Welcome to Propane Point Admin Panel"