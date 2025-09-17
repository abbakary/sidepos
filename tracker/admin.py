from django.contrib import admin
from .models import Customer, Vehicle, Order, InventoryItem

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("code", "full_name", "phone", "customer_type", "total_visits", "last_visit")
    search_fields = ("code", "full_name", "phone", "email")
    list_filter = ("customer_type", "current_status")

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate_number", "customer", "make", "model")
    search_fields = ("plate_number", "make", "model")

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer", "type", "status", "priority", "created_at")
    search_fields = ("order_number", "customer__full_name")
    list_filter = ("type", "status", "priority")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "quantity", "price", "created_at")
    search_fields = ("name", "brand")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)
