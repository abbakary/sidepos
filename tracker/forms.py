import os
import re
import random
import json
from django import forms
from django.contrib.auth.models import User, Group
from .models import Customer, Order, Vehicle, InventoryItem, Profile, InventoryAdjustment

# ... (rest of the code remains the same)

class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = "__all__"
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+256 XXX XXX XXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter address'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes'}),
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'organization_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Organization name'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tax number/TIN'}),
            'personal_subtype': forms.Select(attrs={'class': 'form-select'}),
            'current_status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned = super().clean()
        t = cleaned.get("customer_type")
        if t in {"government","ngo","company"}:
            if not cleaned.get("organization_name"):
                self.add_error("organization_name","Required for organizational customers")
            if not cleaned.get("tax_number"):
                self.add_error("tax_number","Required for organizational customers")
        elif t == "personal":
            if not cleaned.get("personal_subtype"):
                self.add_error("personal_subtype","Please specify if you are the owner or driver")
        return cleaned

class CustomerBasicForm(forms.Form):
    """Step 1: Basic customer information - used for quick customer creation"""
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter customer full name',
            'required': True
        })
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+XXX XXX XXX XXX or 0XXXXXXXXX',
            'required': True
        })
    )

    def clean_phone(self):
        value = (self.cleaned_data.get('phone') or '').strip()
        intl = re.compile(r'^\+\d{3}(?:\s?\d{3}){3}$')
        # Allow local numbers starting with 0 and 9 to 13 digits total
        local = re.compile(r'^0\d{8,12}$')
        if not (intl.match(value) or local.match(value)):
            raise forms.ValidationError('Enter a valid phone number: +XXX XXX XXX XXX or 0XXXXXXXX… (9–13 digits).')
        return value

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com (optional)'
        })
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter customer address (optional)'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional notes (optional)'
        })
    )

class CustomerStep1Form(forms.Form):
    """Step 1: Basic customer information and type"""
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter full name',
            'required': True
        })
    )
    phone = forms.CharField(
        max_length=25,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+255 XXX XXX XXX or 06XXXXXXXX',
            'required': True
        })
    )

    def clean_phone(self):
        value = (self.cleaned_data.get('phone') or '').strip()
        intl = re.compile(r'^\+\d{3}(?:\s?\d{3}){3}$')
        # Allow local numbers starting with 0 and 9 to 13 digits total
        local = re.compile(r'^0\d{8,12}$')
        if not (intl.match(value) or local.match(value)):
            raise forms.ValidationError('Enter a valid phone number: +255 XXX XXX XXX or 0XXXXXXXX… (9–13 digits).')
        return value

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter address'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional notes'
        })
    )
    
    # Customer type fields
    customer_type = forms.ChoiceField(
        choices=Customer.TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'required': True})
    )
    organization_name = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Organization/Company name'
        })
    )
    tax_number = forms.CharField(
        required=False,
        max_length=64,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tax number/TIN'
        })
    )
    personal_subtype = forms.ChoiceField(
        choices=[('', 'Select...')] + Customer.PERSONAL_SUBTYPE,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            choices = list(self.fields['customer_type'].choices)
        except Exception:
            choices = []
        if choices and (not choices[0] or choices[0][0] != ''):
            self.fields['customer_type'].choices = [('', 'Select customer type')] + choices
        self.fields['customer_type'].initial = ''

    def clean(self):
        cleaned = super().clean()
        customer_type = cleaned.get('customer_type')
        
        # Field-level requirements based on customer type
        if customer_type in ['government', 'ngo', 'company']:
            if not cleaned.get('organization_name'):
                self.add_error('organization_name', 'Organization name is required for this customer type')
            if not cleaned.get('tax_number'):
                self.add_error('tax_number', 'Tax number is required for this customer type')
        elif customer_type == 'personal':
            if not cleaned.get('personal_subtype'):
                self.add_error('personal_subtype', 'Please specify if you are the owner or driver')
        
        # Duplicate checks (exact match; no normalization)
        try:
            full_name = (cleaned.get('full_name') or '').strip()
            phone = (cleaned.get('phone') or '').strip()
            org = cleaned.get('organization_name')
            tax = cleaned.get('tax_number')
            from .models import Customer
            qs = Customer.objects.all()
            if customer_type == 'personal':
                if full_name and phone and qs.filter(full_name=full_name, phone=phone, customer_type='personal').exists():
                    self.add_error(None, 'A personal customer with this full name and phone already exists.')
            elif customer_type in ['government', 'ngo', 'company']:
                if full_name and phone and org and tax and qs.filter(
                    full_name=full_name,
                    phone=phone,
                    organization_name=org,
                    tax_number=tax,
                    customer_type=customer_type,
                ).exists():
                    self.add_error(None, 'An organizational customer with the same name, phone, organization and tax number already exists.')
        except Exception:
            # Do not block the form on DB issues; DB constraint still protects uniqueness at save
            pass
        
        return cleaned

class CustomerStep2Form(forms.Form):
    """Step 2: Service intent"""
    INTENT_CHOICES = [
        ("service", "I need a service"),
        ("sales", "I want to buy something"),
        ("inquiry", "Just an inquiry")
    ]
    
    intent = forms.ChoiceField(
        choices=INTENT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )

class CustomerStep3Form(forms.Form):
    """Step 3: Service Type Selection"""
    SERVICE_TYPE_CHOICES = [
        ("tire_sales", "Tire Sales"),
        ("car_service", "Car Service")
    ]

    service_type = forms.ChoiceField(
        choices=SERVICE_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )

class CustomerStep4Form(forms.Form):
    """Step 4: Final confirmation and additional notes"""
    additional_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any additional notes or special requests...'
        })
    )

class CustomerEditForm(forms.ModelForm):
    """Form for editing existing customers"""
    class Meta:
        model = Customer
        fields = ['full_name', 'phone', 'email', 'address', 'notes', 
                 'customer_type', 'organization_name', 'tax_number', 'personal_subtype']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+XXX XXX XXX XXX or 0XXXXXXXXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'organization_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'personal_subtype': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set required fields
        self.fields['full_name'].required = True
        self.fields['phone'].required = True
        self.fields['customer_type'].required = True
        
        # Update choices for customer type
        self.fields['customer_type'].choices = [('', 'Select customer type')] + Customer.TYPE_CHOICES
        
        # Update choices for personal subtype
        self.fields['personal_subtype'].choices = [('', 'Select...')] + Customer.PERSONAL_SUBTYPE
    
    def clean_phone(self):
        value = (self.cleaned_data.get('phone') or '').strip()
        intl = re.compile(r'^\+\d{3}(?:\s?\d{3}){3}$')
        # Allow local numbers starting with 0 and 9 to 13 digits total
        local = re.compile(r'^0\d{8,12}$')
        if not (intl.match(value) or local.match(value)):
            raise forms.ValidationError('Enter a valid phone number: +255 XXX XXX XXX or 0XXXXXXXX… (9–13 digits).')
        return value
    
    def clean(self):
        cleaned = super().clean()
        customer_type = cleaned.get('customer_type')
        
        # Field-level requirements based on customer type
        if customer_type in ['government', 'ngo', 'company']:
            if not cleaned.get('organization_name'):
                self.add_error('organization_name', 'Organization name is required for this customer type')
            if not cleaned.get('tax_number'):
                self.add_error('tax_number', 'Tax number is required for this customer type')
        elif customer_type == 'personal':
            if not cleaned.get('personal_subtype'):
                self.add_error('personal_subtype', 'Please specify if you are the owner or driver')
        
        # Duplicate checks (exact match; no normalization)
        try:
            full_name = (cleaned.get('full_name') or '').strip()
            phone = (cleaned.get('phone') or '').strip()
            org = cleaned.get('organization_name')
            tax = cleaned.get('tax_number')
            from .models import Customer
            qs = Customer.objects.all()
            if customer_type == 'personal':
                if full_name and phone and qs.filter(full_name=full_name, phone=phone, customer_type='personal').exists():
                    self.add_error(None, 'A personal customer with this full name and phone already exists.')
            elif customer_type in ['government', 'ngo', 'company']:
                if full_name and phone and org and tax and qs.filter(
                    full_name=full_name,
                    phone=phone,
                    organization_name=org,
                    tax_number=tax,
                    customer_type=customer_type,
                ).exists():
                    self.add_error(None, 'An organizational customer with the same name, phone, organization and tax number already exists.')
        except Exception:
            # Do not block the form on DB issues; DB constraint still protects uniqueness at save
            pass
        
        return cleaned

class BrandForm(forms.ModelForm):
    """Form for creating and updating brands"""
    class Meta:
        from .models import Brand
        model = Brand
        fields = ['name', 'description', 'website', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter brand name',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter brand description (optional)'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch'
            })
        }
    
    def clean_name(self):
        """Ensure brand name is unique (case-insensitive)"""
        name = self.cleaned_data.get('name')
        if name:
            from .models import Brand
            qs = Brand.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('A brand with this name already exists.')
        return name

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["plate_number", "make", "model", "vehicle_type"]
        widgets = {
            'plate_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., UAH 123A',
                'style': 'text-transform: uppercase;'
            }),
            'make': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Toyota, Honda'
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Camry, Civic'
            }),
            'vehicle_type': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', 'Select vehicle type'),
                ('sedan', 'Sedan'),
                ('suv', 'SUV'),
                ('truck', 'Truck'),
                ('van', 'Van'),
                ('motorcycle', 'Motorcycle'),
                ('bus', 'Bus'),
                ('other', 'Other')
            ])
        }

class OrderForm(forms.ModelForm):
    SERVICE_OPTIONS = [
        ("oil_change", "Oil Change"),
        ("engine_diagnostics", "Engine Diagnostics"),
        ("brake_repair", "Brake Repair"),
        ("tire_rotation", "Tire Rotation"),
        ("wheel_alignment", "Wheel Alignment"),
        ("battery_check", "Battery Check"),
        ("fluid_top_up", "Fluid Top-Up"),
        ("general_maintenance", "General Maintenance"),
    ]

    service_selection = forms.MultipleChoiceField(
        choices=SERVICE_OPTIONS, 
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
            'style': 'display: none;'  # Hide the default checkboxes, we'll style our own
        })
    )

    class Meta:
        model = Order
        fields = [
            "type",
            "vehicle",
            "priority",
            "description",
            "estimated_duration",
            "item_name",
            "brand",
            "quantity",
            "tire_type",
            "inquiry_type",
            "questions",
            "contact_preference",
            "follow_up_date",
        ]
        widgets = {
            "type": forms.Select(attrs={'class': 'form-select'}),
            "vehicle": forms.Select(attrs={'class': 'form-select'}),
            "priority": forms.Select(attrs={'class': 'form-select'}),
            "description": forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the issue or service needed'}),
            "estimated_duration": forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            "item_name": forms.Select(attrs={'class': 'form-select'}),
            "brand": forms.Select(attrs={'class': 'form-select'}),
            "quantity": forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            "tire_type": forms.Select(attrs={'class': 'form-select'}),
            "inquiry_type": forms.Select(attrs={'class': 'form-select'}),
            "questions": forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            "contact_preference": forms.Select(attrs={'class': 'form-select'}),
            "follow_up_date": forms.DateInput(attrs={"type": "date", 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Default estimated duration for service orders
        if not self.fields["estimated_duration"].initial:
            self.fields["estimated_duration"].initial = 50

        # Dynamic item and brand choices from inventory
        try:
            # Get all active inventory items with their brands
            items = InventoryItem.objects.select_related('brand').filter(is_active=True).order_by('name').distinct()
            
            # Create item choices
            name_choices = [('', 'Select item')] + [(item.name, item.name) for item in items if item.name]
            self.fields["item_name"].widget = forms.Select(attrs={'class': 'form-select'}, choices=name_choices)
            
            # Create brand choices using brand names as values
            brand_choices = [('', 'Select brand')]

            # Get all unique brand names from inventory items
            brand_names = set()
            brand_map = {}
            for item in items:
                if item.brand and item.brand.name:
                    brand_names.add(item.brand.name)
                    brand_map[item.name] = item.brand.name

            # Add brands to choices (value = label = brand name)
            brand_choices += sorted([(bn, bn) for bn in brand_names], key=lambda x: x[1])

            # Set brand choices
            self.fields["brand"].widget = forms.Select(attrs={'class': 'form-select'}, choices=brand_choices)

            # Add brand mapping as data attribute for JavaScript
            self.fields["item_name"].widget.attrs['data-brands'] = json.dumps(brand_map)
            
        except Exception as e:
            print(f"Error initializing OrderForm: {str(e)}")
            name_choices = [('', 'Select item')]
            brand_choices = [('', 'Select brand')]
            self.fields["item_name"].widget = forms.Select(attrs={'class': 'form-select'}, choices=name_choices)
            self.fields["brand"].widget = forms.Select(attrs={'class': 'form-select'}, choices=brand_choices)
        
        # Tire type choices
        self.fields["tire_type"].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[
                ('', 'Select condition'),
                ("New", "New"),
                ("Used", "Used"),
                ("Refurbished", "Refurbished")
            ]
        )
        
        # Inquiry type choices
        self.fields["inquiry_type"].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[
                ('', 'Select inquiry type'),
                ("Pricing", "Pricing"),
                ("Services", "Services"),
                ("Appointment Booking", "Appointment Booking"),
                ("General", "General")
            ]
        )
        
        # Contact preference choices
        self.fields["contact_preference"].widget = forms.Select(
            attrs={'class': 'form-select'},
            choices=[
                ('', 'Select preference'),
                ("phone", "Phone"),
                ("email", "Email"),
                ("whatsapp", "WhatsApp")
            ]
        )

    def clean(self):
        cleaned = super().clean()
        t = cleaned.get("type")
        
        if t == "sales":
            for f in ["item_name", "brand"]:
                if not cleaned.get(f):
                    self.add_error(f, "Required for Sales orders")
            q = cleaned.get("quantity")
            if not q or q < 1:
                self.add_error("quantity", "Quantity must be at least 1")
                
        elif t == "service":
            if not cleaned.get("description"):
                self.add_error("description", "Problem description required for Service orders")
            if not cleaned.get("estimated_duration"):
                self.add_error("estimated_duration", "Estimated duration required for Service orders")
            services = cleaned.get("service_selection") or []
            if services:
                desc = cleaned.get("description") or ""
                desc_services = "\nSelected services: " + ", ".join(dict(self.SERVICE_OPTIONS)[s] for s in services)
                cleaned["description"] = (desc + desc_services).strip()
                
        elif t == "consultation":
            if not cleaned.get("inquiry_type"):
                self.add_error("inquiry_type", "Inquiry type is required")
            if not cleaned.get("questions"):
                self.add_error("questions", "Please provide your questions")
                
        return cleaned

class CustomerSearchForm(forms.Form):
    """Form for searching existing customers"""
    search_query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, phone, email, or customer code...',
            'id': 'customer-search'
        })
    )

class InquiryResponseForm(forms.Form):
    """Form for responding to customer inquiries"""
    response = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter your response to the customer...'
        })
    )
    
    follow_up_required = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    follow_up_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

class BrandChoiceField(forms.ModelChoiceField):
    """Custom ModelChoiceField for brand selection with improved display"""
    def label_from_instance(self, obj):
        return obj.name

class InventoryItemForm(forms.ModelForm):
    """Form for creating and updating inventory items"""
    class Meta:
        model = InventoryItem
        fields = ["name", "brand", "description", "quantity", "price", "cost_price", 
                 "sku", "barcode", "reorder_level", "location", "is_active"]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter item name',
                'autofocus': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2,
                'placeholder': 'Enter item description (optional)'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': 0,
                'step': '1'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01', 
                'min': 0,
                'placeholder': '0.00'
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01', 
                'min': 0,
                'placeholder': '0.00'
            }),
            'sku': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SKU (auto-generated if blank)'
            }),
            'barcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Barcode (optional)'
            }),
            'reorder_level': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': 0,
                'step': '1'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Aisle 5, Shelf B'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default quantity to 0 if not set
        if not self.instance.pk and not self.data.get('quantity'):
            self.fields['quantity'].initial = 0
        
        # Only show active brands in the dropdown
        from .models import Brand
        self.fields['brand'] = BrandChoiceField(
            queryset=Brand.objects.filter(is_active=True).order_by('name'),
            empty_label="Select a brand or add new",
            widget=forms.Select(attrs={
                'class': 'form-select',
                'data-control': 'select2',
                'data-placeholder': 'Select a brand or add new',
                'data-allow-clear': 'true',
                'data-tags': 'true',
                'data-token-separators': '[\",\"]',
                'data-create-option': 'true',
                'data-ajax--url': '/inventory/api/brands/create/'
            }),
            required=True
        )
        
        # Add help text
        self.fields['brand'].help_text = 'Select an existing brand or <a href="#" data-bs-toggle="modal" data-bs-target="#addBrandModal">add a new one</a>'
        self.fields['brand'].help_text_format = 'html'
        
        # Set default values for new items
        if not self.instance.pk:
            self.fields['is_active'].initial = True
            self.fields['reorder_level'].initial = 5
    
    def clean_sku(self):
        """Generate SKU if not provided"""
        sku = self.cleaned_data.get('sku')
        if sku is not None:
            sku = sku.strip()
        if not sku and self.cleaned_data.get('name') and self.cleaned_data.get('brand'):
            # Generate a simple SKU: first 3 chars of brand + first 3 chars of name + random 4 digits
            brand = str(self.cleaned_data['brand'])[:3].upper()
            name = ''.join([c for c in self.cleaned_data['name'] if c.isalnum()])[:3].upper()
            sku = f"{brand}-{name}-{random.randint(1000, 9999)}"
        return sku or ''
    
    def clean_price(self):
        """Ensure price is not negative"""
        price = self.cleaned_data.get('price', 0)
        if price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price
    
    def clean_quantity(self):
        """Ensure quantity is not negative"""
        quantity = self.cleaned_data.get('quantity', 0)
        if quantity < 0:
            raise forms.ValidationError("Quantity cannot be negative.")
        return quantity

    def save(self, commit=True):
        # Generate SKU if not provided
        if not self.cleaned_data.get('sku') and self.cleaned_data.get('name') and self.cleaned_data.get('brand'):
            brand = str(self.cleaned_data['brand'])[:3].upper()
            name = ''.join([c for c in self.cleaned_data['name'] if c.isalnum()])[:3].upper()
            self.instance.sku = f"{brand}-{name}-{random.randint(1000, 9999)}"
        
        return super().save(commit)

class AdminUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    group_manager = forms.BooleanField(
        required=False,
        label="Manager role",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "is_staff", "is_superuser"]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'checked': True}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Passwords do not match')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        mgr, _ = Group.objects.get_or_create(name="manager")
        if self.cleaned_data.get('group_manager'):
            user.groups.add(mgr)
        return user

class AdminUserForm(forms.ModelForm):
    group_manager = forms.BooleanField(
        required=False,
        label="Manager role",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    new_password = forms.CharField(
        required=False,
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        required=False,
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "is_staff", "is_superuser"]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            mgr = Group.objects.get(name="manager")
            self.fields['group_manager'].initial = self.instance and self.instance.pk and self.instance.groups.filter(id=mgr.id).exists()
        except Group.DoesNotExist:
            pass

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('confirm_password')
        if p1 or p2:
            if p1 != p2:
                self.add_error('confirm_password', 'Passwords do not match')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        mgr, _ = Group.objects.get_or_create(name="manager")
        if self.cleaned_data.get('group_manager'):
            user.groups.add(mgr)
        else:
            user.groups.remove(mgr)
        p1 = self.cleaned_data.get('new_password')
        if p1:
            user.set_password(p1)
            user.save()
        return user

class InventoryAdjustmentForm(forms.ModelForm):
    """Form for making inventory adjustments (add/remove stock)"""
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True,
            'data-placeholder': 'Select an item',
            'data-allow-clear': 'true'
        })
    )
    
    adjustment_type = forms.ChoiceField(
        choices=InventoryAdjustment.ADJUSTMENT_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter quantity',
            'required': True
        })
    )
    
    reference = forms.CharField(
        required=False,
        max_length=64,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reference number (optional)'
        })
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Reason for adjustment (optional)'
        })
    )
    
    class Meta:
        model = InventoryAdjustment
        fields = ['item', 'adjustment_type', 'quantity', 'reference', 'notes']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default adjustment type
        self.fields['adjustment_type'].initial = 'addition'
        
        # Set the queryset for the item field
        self.fields['item'].queryset = InventoryItem.objects.filter(is_active=True).order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        adjustment_type = cleaned_data.get('adjustment_type')
        quantity = cleaned_data.get('quantity', 0)
        
        # For removal or damage, check if enough stock is available
        if item and adjustment_type in ['removal', 'damage']:
            if quantity > item.quantity:
                self.add_error('quantity', f'Not enough stock. Only {item.quantity} available.')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set the user who made the adjustment
        if self.user:
            instance.adjusted_by = self.user
        
        # Calculate quantities
        instance.previous_quantity = instance.item.quantity
        
        # For removal or damage, make quantity negative
        if instance.adjustment_type in ['removal', 'damage']:
            instance.quantity = -abs(instance.quantity)
        
        # Calculate new quantity
        instance.new_quantity = instance.previous_quantity + instance.quantity
        
        if commit:
            # Save the adjustment
            instance.save()
            
            # Update the item's quantity
            instance.item.quantity = instance.new_quantity
            instance.item.save(update_fields=['quantity'])
        
        return instance


class SystemSettingsForm(forms.Form):
    company_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company/Workshop name'})
    )
    default_priority = forms.ChoiceField(
        choices=[('low','Low'),('medium','Medium'),('high','High'),('urgent','Urgent')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    enable_unbranded_alias = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    allow_order_without_vehicle = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    sms_provider = forms.ChoiceField(
        choices=[('none','None'),('zapier','Zapier Webhook'),('twilio','Twilio')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['photo']
        widgets = {
            'photo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'onchange': 'previewImage(this)'
            })
        }
    
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Last name'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
    
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            # Validate file size (2MB max)
            max_size = 2 * 1024 * 1024
            if photo.size > max_size:
                raise forms.ValidationError('Image file too large (max 2MB)')
            
            # Validate file type
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = os.path.splitext(photo.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError('Unsupported file type. Please upload a valid image file.')
        return photo
    
    def save(self, user=None, commit=True):
        """Save profile and uploaded photo safely.
        - Update user's first/last name if provided
        - Save new photo first, then delete the old one to avoid file-handle issues
        """
        # Update user fields if user is provided
        if user is not None:
            user.first_name = self.cleaned_data.get('first_name', '')
            user.last_name = self.cleaned_data.get('last_name', '')
            user.save()

        # Prepare instance via ModelForm machinery
        profile = super(ProfileForm, self).save(commit=False)

        # Keep reference to old photo to delete later (only if changed)
        old_photo = None
        if profile.pk:
            try:
                old_photo = type(profile).objects.only('photo').get(pk=profile.pk).photo
            except type(profile).DoesNotExist:
                old_photo = None

        if commit:
            # Saving here will persist the new uploaded file if provided
            profile.save()
            # Delete old photo after successful save and only if it changed
            if 'photo' in self.changed_data and old_photo and old_photo.name and (
                not profile.photo or old_photo.name != profile.photo.name
            ):
                old_photo.delete(save=False)

        return profile
