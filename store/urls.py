from django.urls import path
from . import views

urlpatterns = [
    # ==================== AUTHENTICATION ====================
    path("", views.home, name="home"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    
    # ==================== DASHBOARD (ROUTING) ====================
    path("dashboard/", views.dashboard, name="dashboard"),
    
    # ==================== CUSTOMER PORTAL ====================
    path("map/", views.map, name="map"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("orders/<int:reservation_id>/cancel/", views.cancel_order, name="cancel_order"),
    path("store/<int:store_id>/", views.store_detail, name="store_detail"),
    path("reserve/<int:tank_id>/", views.reserve_tank, name="reserve_tank"),
    path("receipt/<int:reservation_id>/", views.receipt, name="receipt"),
    path("notifications/", views.notifications, name="notifications"),
    
    # ==================== SELLER APPLICATION ====================
    path("apply-seller/", views.apply_seller, name="apply_seller"),
    path("seller/pending/", views.seller_pending, name="seller_pending"),
    
    # ==================== SELLER PORTAL ====================
    path("seller/stores/", views.my_stores, name="my_stores"),
    path("seller/store/create/", views.create_store, name="create_store"),
    path("seller/store/<int:store_id>/manage/", views.manage_store, name="manage_store"),
    path("seller/store/<int:store_id>/delete/", views.delete_store, name="delete_store"),
    
    # ==================== SELLER - UPLOAD PICKUP PROOF ====================
    path("seller/order/<int:reservation_id>/upload-pickup-proof/", views.upload_pickup_proof, name="upload_pickup_proof"),
    
    # ==================== ADMIN PORTAL ====================
    # Changed from "admin/" to "management/" to avoid conflict with Django admin
    path("management/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    
    # Admin - Seller Applications
    path("management/applications/", views.admin_applications, name="admin_applications"),
    path("management/applications/<int:application_id>/review/", views.admin_review_application, name="admin_review_application"),
    
    # Admin - Manage Sellers
    path("management/sellers/", views.admin_sellers, name="admin_sellers"),
    path("management/sellers/<int:user_id>/suspend/", views.admin_suspend_seller, name="admin_suspend_seller"),
    
    # Admin - Manage Stores
    path("management/stores/", views.admin_stores, name="admin_stores"),
    path("management/stores/<int:store_id>/toggle/", views.admin_toggle_store, name="admin_toggle_store"),
    
    # Admin - Manage Orders & Review Pickup Proofs
    path("management/orders/", views.admin_orders, name="admin_orders"),
    path("management/orders/<int:reservation_id>/review-pickup/", views.admin_review_pickup, name="admin_review_pickup"),
]