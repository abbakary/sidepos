from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.contrib.auth.views import LogoutView
from . import views
from .views import CustomLoginView, CustomLogoutView

app_name = "tracker"

urlpatterns = [
    # Authentication
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    
    # Main app
    path("", views.dashboard, name="dashboard"),
    path("customers/", views.customers_list, name="customers_list"),
    path("customers/search/", views.customers_search, name="customers_search"),
    path("customers/quick-create/", views.customers_quick_create, name="customers_quick_create"),
    path("customers/register/", views.customer_register, name="customer_register"),
    path("customers/export/", views.customers_export, name="customers_export"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
    path("customers/<int:pk>/note/", views.add_customer_note, name="add_customer_note"),
    path("customers/<int:customer_id>/note/<int:note_id>/delete/", views.delete_customer_note, name="delete_customer_note"),
    path("customers/<int:pk>/order/new/", views.create_order_for_customer, name="create_order_for_customer"),
    path("customer-groups/", views.customer_groups, name="customer_groups"),
    path("customer-groups/export/", views.customer_groups_export, name="customer_groups_export"),
    path("api/customer-groups/data/", views.customer_groups_data, name="customer_groups_data"),

    path("orders/", views.orders_list, name="orders_list"),
    path("orders/export/", views.orders_export, name="orders_export"),
    path("orders/new/", views.start_order, name="order_start"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/edit/", views.order_edit, name="order_edit"),
    path("orders/<int:pk>/delete/", views.order_delete, name="order_delete"),
    path("orders/<int:pk>/status/", views.update_order_status, name="update_order_status"),

    path("analytics/", views.analytics, name="analytics"),
    path("analytics/customer/", views.analytics_customer, name="analytics_customer"),
    path("analytics/service/", views.analytics_service, name="analytics_service"),

    # Temporarily route performance analytics to the main analytics page until the view is implemented
   

    # Reports
    path("reports/", views.reports, name="reports"),
    path("reports/advanced/", views.reports_advanced, name="reports_advanced"),
    path("reports/export/", views.reports_export, name="reports_export"),

    # Inquiry management
    path("inquiries/", views.inquiries, name="inquiries"),
    path("inquiries/<int:pk>/", views.inquiry_detail, name="inquiry_detail"),
    path("inquiries/<int:pk>/respond/", views.inquiry_respond, name="inquiry_respond"),
    path("inquiries/<int:pk>/status/", views.update_inquiry_status, name="update_inquiry_status"),

    # Inventory (manager/admin)
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/new/", views.inventory_create, name="inventory_create"),
    path("inventory/<int:pk>/edit/", views.inventory_edit, name="inventory_edit"),
    path("inventory/<int:pk>/delete/", views.inventory_delete, name="inventory_delete"),
    path("inventory/stock-management/", views.inventory_stock_management, name="inventory_stock_management"),
    path("inventory/low-stock/", views.inventory_low_stock, name="inventory_low_stock"),


    # Admin-only Organization Management
    path("organization/", views.organization_management, name="organization"),
    path("organization/export/", views.organization_export, name="organization_export"),

    # Vehicle management
    path("vehicles/<int:customer_id>/add/", views.vehicle_add, name="vehicle_add"),
    path("vehicles/<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
    path("vehicles/<int:pk>/delete/", views.vehicle_delete, name="vehicle_delete"),
    path("api/customers/<int:customer_id>/vehicles/", views.api_customer_vehicles, name="api_customer_vehicles"),

    # User management (admin)
    path("users/", views.users_list, name="users_list"),
    path("users/add/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/toggle/", views.user_toggle_active, name="user_toggle_active"),
    path("users/<int:pk>/reset/", views.user_reset_password, name="user_reset_password"),

    # Internal admin console: system settings and tools
    path("console/settings/", views.system_settings, name="system_settings"),
    path("console/audit-logs/", views.audit_logs, name="audit_logs"),
    path("console/backup/", views.backup_restore, name="backup_restore"),

    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),

    path("api/orders/recent/", views.api_recent_orders, name="api_recent_orders"),
    path("api/inventory/items/", views.api_inventory_items, name="api_inventory_items"),
    path("api/inventory/brands/", views.api_inventory_brands, name="api_inventory_brands"),
    path("api/inventory/stock/", views.api_inventory_stock, name="api_inventory_stock"),
    path("api/brands/create/", views.create_brand, name="api_create_brand"),
    path("api/customers/<int:customer_id>/vehicles/", views.api_customer_vehicles, name="api_customer_vehicles"),
    # Notifications summary (canonical)
    path("api/notifications/summary/", views.api_notifications_summary, name="api_notifications_summary"),
    # Aliases to tolerate typos/missing trailing slash
    path("api/notifications/summary", views.api_notifications_summary),
    path("api/notification/summary/", views.api_notifications_summary, name="api_notifications_summary_singular"),
    path("api/notification/summary", views.api_notifications_summary),
    path("api/customers/check-duplicate/", views.api_check_customer_duplicate, name="api_check_customer_duplicate"),
]
