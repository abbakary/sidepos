from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
import uuid


class Customer(models.Model):
    TYPE_CHOICES = [
        ("government", "Government"),
        ("ngo", "NGO"),
        ("company", "Private Company"),
        ("personal", "Personal"),
        ("bodaboda", "Bodaboda"),
    ]
    PERSONAL_SUBTYPE = [("owner", "Owner"), ("driver", "Driver")]
    STATUS_CHOICES = [
        ("arrived", "Arrived"),
        ("in_service", "In Service"),
        ("completed", "Completed"),
        ("departed", "Departed"),
    ]

    code = models.CharField(max_length=32, unique=True, editable=False)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # keep this as "notes" so your forms work, but mark as deprecated
    notes = models.TextField(
        blank=True,
        null=True,
        help_text='General notes about the customer (deprecated, use CustomerNote model instead)'
    )

    customer_type = models.CharField(max_length=20, choices=TYPE_CHOICES, null=True, blank=True)
    organization_name = models.CharField(max_length=255, blank=True, null=True)
    tax_number = models.CharField(max_length=64, blank=True, null=True)
    personal_subtype = models.CharField(max_length=16, choices=PERSONAL_SUBTYPE, blank=True, null=True)

    registration_date = models.DateTimeField(default=timezone.now)
    arrival_time = models.DateTimeField(blank=True, null=True)
    current_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="arrived")

    total_visits = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_visit = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"CUST{str(uuid.uuid4())[:8].upper()}"
            while Customer.objects.filter(code=self.code).exists():
                self.code = f"CUST{str(uuid.uuid4())[:8].upper()}"
        if not self.arrival_time:
            self.arrival_time = timezone.now()
        super().save(*args, **kwargs)

    def get_icon_for_customer_type(self):
        """Return appropriate icon class based on customer type"""
        if not self.customer_type:
            return 'user'
        
        icon_map = {
            'government': 'landmark',
            'ngo': 'hands-helping',
            'company': 'building',
            'personal': 'user',
            'bodaboda': 'motorcycle',
        }
        return icon_map.get(self.customer_type, 'user')
        
    def __str__(self):
        return f"{self.full_name} ({self.code})"

    class Meta:
        indexes = [
            models.Index(fields=["full_name"], name="idx_cust_name"),
            models.Index(fields=["phone"], name="idx_cust_phone"),
            models.Index(fields=["email"], name="idx_cust_email"),
            models.Index(fields=["registration_date"], name="idx_cust_reg"),
            models.Index(fields=["last_visit"], name="idx_cust_lastvisit"),
            models.Index(fields=["customer_type"], name="idx_cust_type"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["full_name", "phone", "organization_name", "tax_number"],
                name="uniq_customer_identity",
            )
        ]


class Vehicle(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="vehicles")
    plate_number = models.CharField(max_length=32)
    make = models.CharField(max_length=64, blank=True, null=True)
    model = models.CharField(max_length=64, blank=True, null=True)
    vehicle_type = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.plate_number} - {self.make or ''} {self.model or ''}"

    class Meta:
        indexes = [
            models.Index(fields=["customer"], name="idx_vehicle_customer"),
            models.Index(fields=["plate_number"], name="idx_vehicle_plate"),
        ]


class Order(models.Model):
    TYPE_CHOICES = [("service", "Service"), ("sales", "Sales"), ("consultation", "Consultation")]
    STATUS_CHOICES = [
        ("created", "Created"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")]

    order_number = models.CharField(max_length=32, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="created")
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default="medium")

    description = models.TextField(blank=True, null=True)
    estimated_duration = models.PositiveIntegerField(blank=True, null=True, help_text="Minutes")
    actual_duration = models.PositiveIntegerField(blank=True, null=True)

    # Sales fields
    item_name = models.CharField(max_length=64, blank=True, null=True)
    brand = models.CharField(max_length=64, blank=True, null=True)
    quantity = models.PositiveIntegerField(blank=True, null=True)
    tire_type = models.CharField(max_length=32, blank=True, null=True)

    # Consultation fields
    inquiry_type = models.CharField(max_length=64, blank=True, null=True)
    questions = models.TextField(blank=True, null=True)
    contact_preference = models.CharField(max_length=16, blank=True, null=True)
    follow_up_date = models.DateField(blank=True, null=True)

    # Timestamps and assignment
    created_at = models.DateTimeField(default=timezone.now)
    assigned_at = models.DateTimeField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_orders")

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if not self.order_number:
            self.order_number = f"ORD{str(uuid.uuid4())[:8].upper()}"
            while Order.objects.filter(order_number=self.order_number).exists():
                self.order_number = f"ORD{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)
        if creating:
            self.customer.total_visits = (self.customer.total_visits or 0) + 1
            self.customer.last_visit = timezone.now()
            self.customer.save()

    def __str__(self):
        return f"{self.order_number} - {self.customer.full_name}"

    class Meta:
        indexes = [
            models.Index(fields=["status"], name="idx_order_status"),
            models.Index(fields=["type"], name="idx_order_type"),
            models.Index(fields=["priority"], name="idx_order_priority"),
            models.Index(fields=["created_at"], name="idx_order_created"),
            models.Index(fields=["completed_at"], name="idx_order_completed"),
            models.Index(fields=["customer", "created_at"], name="idx_order_cust_created"),
            models.Index(fields=["type", "status"], name="idx_order_type_status"),
        ]


class CustomerNote(models.Model):
    """Model to store notes for customers"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='notes_history')
    note = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='notes_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer Note'
        verbose_name_plural = 'Customer Notes'

    def __str__(self):
        return f'Note for {self.customer.full_name} by {self.created_by.username if self.created_by else "System"}'


class Brand(models.Model):
    """Brand model to represent different product brands"""
    name = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='brand_logos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=["name"], name="idx_brand_name"),
            models.Index(fields=["is_active"], name="idx_brand_active"),
        ]

class InventoryItem(models.Model):
    """Inventory item that belongs to a specific brand"""
    name = models.CharField(max_length=128)
    brand = models.ForeignKey(
        Brand, 
        on_delete=models.PROTECT,  # Prevent deletion of brand if items exist
        related_name="items",
        help_text="Product brand"
    )
    description = models.TextField(blank=True, null=True)
    quantity = models.PositiveIntegerField(
        default=0,
        help_text="Current stock quantity"
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Selling price per unit"
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Purchase cost per unit"
    )
    sku = models.CharField(
        max_length=64, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="Stock Keeping Unit"
    )
    barcode = models.CharField(
        max_length=64, 
        blank=True, 
        null=True,
        help_text="Barcode (UPC, EAN, etc.)"
    )
    reorder_level = models.PositiveIntegerField(
        default=5, 
        help_text="Quantity at which to reorder"
    )
    location = models.CharField(
        max_length=64, 
        blank=True, 
        null=True,
        help_text="Storage location in warehouse"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Is this item currently available for sale?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.brand.name} - {self.name}"

    @property
    def needs_reorder(self):
        return self.quantity <= self.reorder_level

    class Meta:
        ordering = ['brand__name', 'name']
        indexes = [
            models.Index(fields=["name"], name="idx_item_name"),
            models.Index(fields=["brand"], name="idx_item_brand"),
            models.Index(fields=["name", "brand"], name="idx_item_name_brand"),
            models.Index(fields=["created_at"], name="idx_item_created"),
            models.Index(fields=["sku"], name="idx_item_sku"),
            models.Index(fields=["barcode"], name="idx_item_barcode"),
        ]
        unique_together = [['name', 'brand']]


class InventoryAdjustment(models.Model):
    """Tracks all inventory adjustments (additions, removals, corrections)"""
    ADJUSTMENT_TYPES = [
        ('addition', 'Stock Addition'),
        ('removal', 'Stock Removal'),
        ('correction', 'Quantity Correction'),
        ('damage', 'Damaged Goods'),
        ('return', 'Customer Return'),
    ]

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='adjustments',
        help_text='The inventory item being adjusted'
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=ADJUSTMENT_TYPES,
        help_text='Type of adjustment being made'
    )
    quantity = models.IntegerField(
        help_text='Positive for additions, negative for removals'
    )
    previous_quantity = models.IntegerField(
        help_text='Quantity before adjustment'
    )
    new_quantity = models.IntegerField(
        help_text='Quantity after adjustment'
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text='Reason for adjustment or additional notes'
    )
    adjusted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventory_adjustments',
        help_text='User who made this adjustment'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text='Optional reference number or ID for tracking'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['item', 'created_at']),
            models.Index(fields=['adjustment_type']),
            models.Index(fields=['reference']),
        ]

    def __str__(self):
        return f"{self.get_adjustment_type_display()} - {self.item.name} ({self.quantity:+d})"

    def save(self, *args, **kwargs):
        # Calculate previous and new quantities
        if not self.pk:  # Only for new records
            self.previous_quantity = self.item.quantity
            self.new_quantity = self.previous_quantity + self.quantity
            
            # Update the inventory item quantity
            self.item.quantity = self.new_quantity
            self.item.save(update_fields=['quantity'])
            
            # Ensure adjusted_by is set if not provided
            if not self.adjusted_by_id and hasattr(self.item, '_current_user'):
                self.adjusted_by = self.item._current_user
        
        super().save(*args, **kwargs)


def user_avatar_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/avatars/user_<id>/<filename>
    return f'avatars/user_{instance.user.id}/{filename}'

class Profile(models.Model):
    """User profile storing extra fields like photo and preferences."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    photo = models.ImageField(upload_to=user_avatar_path, blank=True, null=True, help_text='User profile picture')
    timezone = models.CharField(max_length=100, default='UTC', help_text='User timezone for displaying dates and times')

    def __str__(self):
        return f"{self.user.username}'s profile"
