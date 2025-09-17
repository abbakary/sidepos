import json
from django import http
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Count, Avg, Q, Sum, Case, When, F, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, TruncDay, TruncMonth, Concat
from django.utils import timezone
from django.contrib.auth.views import LoginView
from .forms import ProfileForm, CustomerStep1Form, CustomerStep2Form, CustomerStep3Form, CustomerStep4Form, VehicleForm, OrderForm, CustomerEditForm, SystemSettingsForm, BrandForm
from django.urls import reverse
from django.contrib import messages
from django.core.cache import cache
import json
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from .models import Profile, Customer, Order, Vehicle, InventoryItem, CustomerNote, Brand
from django.core.paginator import Paginator
from .utils import add_audit_log, get_audit_logs, clear_audit_logs
from datetime import datetime, timedelta



from django.contrib.auth.views import LogoutView
from django.views.generic import View

class CustomLoginView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = self.request.POST.get("remember")
        if not remember:
            self.request.session.set_expiry(0)
        else:
            self.request.session.set_expiry(60 * 60 * 24 * 14)
        try:
            from .signals import _client_ip
            ip = _client_ip(self.request)
            ua = (self.request.META.get('HTTP_USER_AGENT') or '')[:200]
            add_audit_log(self.request.user, 'login', f'Login at {timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")} from {ip or "?"} UA: {ua}', ip=ip, user_agent=ua)
        except Exception:
            pass
        return response

    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return reverse('tracker:dashboard')
        if user.groups.filter(name='manager').exists():
            return reverse('tracker:orders_list')
        if user.is_staff:
            return reverse('tracker:users_list')
        return reverse('tracker:dashboard')

class CustomLogoutView(LogoutView):
    next_page = 'login'  # This will use the URL name 'login' for redirection
    
    def dispatch(self, request, *args, **kwargs):
        try:
            from .signals import _client_ip
            ip = _client_ip(request)
            ua = (request.META.get('HTTP_USER_AGENT') or '')[:200]
            add_audit_log(request.user, 'logout', f'Logout at {timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")}', ip=ip, user_agent=ua)
        except Exception:
            pass
        return super().dispatch(request, *args, **kwargs)


@login_required
def dashboard(request: HttpRequest):
    # Cache only heavy metrics; refresh dynamic sections every request
    cache_key = "dashboard_metrics_v3"
    metrics = cache.get(cache_key)

    today = timezone.localdate()

    if not metrics:
        total_orders = Order.objects.count()
        total_customers = Customer.objects.count()

        status_counts_qs = Order.objects.values("status").annotate(c=Count("id"))
        type_counts_qs = Order.objects.values("type").annotate(c=Count("id"))
        priority_counts_qs = Order.objects.values("priority").annotate(c=Count("id"))

        status_counts = {x["status"]: x["c"] for x in status_counts_qs}
        type_counts = {x["type"]: x["c"] for x in type_counts_qs}
        priority_counts = {x["priority"]: x["c"] for x in priority_counts_qs}

        # Ensure we have a count for completed orders, even if it's zero
        completed_orders = Order.objects.filter(status="completed").count()
        completion_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Update status_counts to ensure 'completed' key exists
        status_counts['completed'] = completed_orders

        # New customers this month
        new_customers_this_month = Customer.objects.filter(
            registration_date__year=today.year,
            registration_date__month=today.month,
        ).count()

        # Keep original fields/logic for compatibility, but use valid types/statuses
        average_order_value = 0
        pending_inquiries_count = Order.objects.filter(
            type="consultation",
            status__in=["created", "assigned", "in_progress"],
        ).count()

        # Upcoming appointments (next 7 days) based on active orders
        upcoming_appointments = (
            Order.objects.filter(
                status__in=["created", "assigned", "in_progress"],
                created_at__date__gte=today,
                created_at__date__lte=today + timedelta(days=7),
            )
            .select_related("customer")
            .order_by("created_at")[:5]
        )

        # Top customers by order count
        from django.db.models import Max

        top_customers = (
            Customer.objects.annotate(
                order_count=Count("orders"),
                latest_order_date=Max("orders__created_at")
            )
            .filter(order_count__gt=0)
            .order_by("-order_count")[:5]
        )

        status_percentages = {}
        for s, c in status_counts.items():
            status_percentages[f"{s}_percent"] = (c / total_orders * 100) if total_orders > 0 else 0

        # Get inventory metrics
        from django.db.models import Sum, Q
        from tracker.models import InventoryItem
        
        # Total inventory items count
        total_inventory_items = InventoryItem.objects.count()
        
        # Sum of all quantities in stock
        total_stock = InventoryItem.objects.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Count of low stock items (quantity <= reorder_level)
        low_stock_count = InventoryItem.objects.filter(quantity__lte=F('reorder_level')).count()
        
        # Count of out of stock items
        out_of_stock_count = InventoryItem.objects.filter(quantity=0).count()
        
        metrics = {
            'total_orders': total_orders,
            'completed_orders': completed_orders,  # Add this line to include completed orders count
            'total_customers': total_customers,
            'completion_rate': round(completion_rate, 1),
            'status_counts': status_counts,
            'type_counts': type_counts,
            'priority_counts': priority_counts,
            'new_customers_this_month': new_customers_this_month,
            'pending_inquiries_count': pending_inquiries_count,
            'average_order_value': average_order_value,
            'upcoming_appointments': list(upcoming_appointments.values('id', 'customer__full_name', 'created_at')),
            'top_customers': list(top_customers.values('id', 'full_name', 'order_count', 'phone', 'email', 'total_spent', 'latest_order_date')),
            'recent_orders': list(Order.objects.select_related("customer").exclude(status="completed").order_by("-created_at").values('id', 'customer__full_name', 'status', 'created_at')[:10]),
            'inventory_metrics': {
                'total_items': total_inventory_items,
                'total_stock': total_stock,
                'low_stock_count': low_stock_count,
                'out_of_stock_count': out_of_stock_count,
            }
        }
        cache.set(cache_key, metrics, 60)

    # Always fresh data for fast-updating sections
    recent_orders = (
        Order.objects.select_related("customer").exclude(status="completed").order_by("-created_at")[:10]
    )
    completed_today = Order.objects.filter(status="completed", completed_at__date=today).count()

    context = {**metrics, "recent_orders": recent_orders, "completed_today": completed_today, "current_time": timezone.now()}
    # render after charts

    # Build sales_chart_json (monthly Orders vs Completed for last 12 months)
    from django.db.models.functions import TruncMonth

    # Last 12 months for type 'sales'
    last_months = [(today.replace(day=1) - timezone.timedelta(days=1)).replace(day=1)]
    for _ in range(11):
        prev = (last_months[-1] - timezone.timedelta(days=1)).replace(day=1)
        last_months.append(prev)
    last_months = list(reversed(last_months))

    monthly_total_qs = Order.objects.filter(type="sales").annotate(m=TruncMonth("created_at")).values("m").annotate(c=Count("id"))
    monthly_completed_qs = Order.objects.filter(type="sales", status="completed").annotate(m=TruncMonth("completed_at")).values("m").annotate(c=Count("id"))
    monthly_total_map = {row["m"].date(): row["c"] for row in monthly_total_qs if row["m"]}
    monthly_completed_map = {row["m"].date(): row["c"] for row in monthly_completed_qs if row["m"]}

    def _month_label(d):
        return d.strftime("%b %Y")

    sales_chart = {
        "labels": [_month_label(m) for m in last_months],
        "total": [monthly_total_map.get(m, 0) for m in last_months],
        "completed": [monthly_completed_map.get(m, 0) for m in last_months],
    }

    # Periodized datasets
    curr_month_start = today.replace(day=1)
    curr_days = [curr_month_start + timezone.timedelta(days=i) for i in range((today - curr_month_start).days + 1)]

    daily_total_prev_qs = Order.objects.filter(type="sales", created_at__date__gte=curr_month_start, created_at__date__lte=today).annotate(d=TruncDate("created_at")).values("d").annotate(c=Count("id"))
    daily_completed_prev_qs = Order.objects.filter(type="sales", status="completed", completed_at__date__gte=curr_month_start, completed_at__date__lte=today).annotate(d=TruncDate("completed_at")).values("d").annotate(c=Count("id"))
    daily_total_prev_map = {row["d"]: row["c"] for row in daily_total_prev_qs if row["d"]}
    daily_completed_prev_map = {row["d"]: row["c"] for row in daily_completed_prev_qs if row["d"]}
    sales_last_month = {
        "labels": [d.strftime("%Y-%m-%d") for d in curr_days],
        "total": [daily_total_prev_map.get(d, 0) for d in curr_days],
        "completed": [daily_completed_prev_map.get(d, 0) for d in curr_days],
    }

    last_7_days = [today - timezone.timedelta(days=i) for i in range(6, -1, -1)]
    daily_total_qs = Order.objects.filter(type="sales").annotate(d=TruncDate("created_at")).values("d").annotate(c=Count("id"))
    daily_completed_qs = Order.objects.filter(type="sales", status="completed").annotate(d=TruncDate("completed_at")).values("d").annotate(c=Count("id"))
    daily_total_map = {row["d"]: row["c"] for row in daily_total_qs if row["d"]}
    daily_completed_map = {row["d"]: row["c"] for row in daily_completed_qs if row["d"]}
    sales_last_week = {
        "labels": [d.strftime("%Y-%m-%d") for d in last_7_days],
        "total": [daily_total_map.get(d, 0) for d in last_7_days],
        "completed": [daily_completed_map.get(d, 0) for d in last_7_days],
    }

    from django.db.models.functions import TruncHour
    hourly_total_qs = Order.objects.filter(type="sales", created_at__date=today).annotate(h=TruncHour("created_at")).values("h").annotate(c=Count("id"))
    hourly_completed_qs = Order.objects.filter(type="sales", status="completed", completed_at__date=today).annotate(h=TruncHour("completed_at")).values("h").annotate(c=Count("id"))
    hourly_total_map = {row["h"].hour: row["c"] for row in hourly_total_qs if row["h"]}
    hourly_completed_map = {row["h"].hour: row["c"] for row in hourly_completed_qs if row["h"]}
    hours = list(range(0, 24))
    sales_today = {"labels": [f"{h:02d}:00" for h in hours], "total": [hourly_total_map.get(h, 0) for h in hours], "completed": [hourly_completed_map.get(h, 0) for h in hours]}

    sales_periods = {"last_year": sales_chart, "last_month": sales_last_month, "last_week": sales_last_week, "today": sales_today}

    # Sparkline last 8 days
    last_8_days = [today - timezone.timedelta(days=i) for i in range(7, -1, -1)]
    total_order_spark = {
        "labels": [d.strftime("%Y-%m-%d") for d in last_8_days],
        "total": [daily_total_map.get(d, 0) for d in last_8_days],
        "completed": [daily_completed_map.get(d, 0) for d in last_8_days],
    }

    # Top customers by orders per period
    def _period_range(name):
        if name == "today":
            return today, today
        if name == "yesterday":
            y = today - timezone.timedelta(days=1)
            return y, y
        if name == "last_week":
            return today - timezone.timedelta(days=6), today
        # last_month (previous calendar month)
        start = (today.replace(day=1) - timezone.timedelta(days=1)).replace(day=1)
        end = today.replace(day=1) - timezone.timedelta(days=1)
        return start, end

    top_orders_json_data = {}
    for p in ["today", "yesterday", "last_week", "last_month"]:
        start_d, end_d = _period_range(p)
        rows = (
            Order.objects.filter(created_at__date__gte=start_d, created_at__date__lte=end_d)
            .values("customer__full_name")
            .annotate(c=Count("id"))
            .order_by("-c")[:5]
        )
        top_orders_json_data[p] = {
            "labels": [r["customer__full_name"] or "Unknown" for r in rows],
            "values": [r["c"] for r in rows],
        }

    # Add inventory metrics to context
    inventory_metrics = metrics.get('inventory_metrics', {})
    
    context = {
        **metrics,
        "recent_orders": recent_orders,
        "completed_today": completed_today,
        "current_time": timezone.now(),
        "sales_chart_json": json.dumps(sales_chart),
        "sales_chart_periods_json": json.dumps(sales_periods),
        "total_order_spark_json": json.dumps(total_order_spark),
        "top_orders_json": json.dumps(top_orders_json_data),
        "inventory_metrics": inventory_metrics,  # Add inventory metrics to template context
    }
    return render(request, "tracker/dashboard.html", context)


@login_required
def customers_list(request: HttpRequest):
    from django.db.models import Q
    q = request.GET.get('q','').strip()
    f_type = request.GET.get('type','').strip()
    f_status = request.GET.get('status','').strip()

    from django.db.models import Count

    qs = Customer.objects.all().annotate(
        returning_dates=Count('orders__created_at__date', distinct=True)
    ).order_by('-registration_date')
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q) | Q(code__icontains=q)
        )
    if f_type:
        qs = qs.filter(customer_type=f_type)
    if f_status == 'active':
        qs = qs.filter(total_visits__gt=0)
    elif f_status == 'inactive':
        qs = qs.filter(total_visits__lte=0)
    elif f_status == 'returning':
        qs = qs.filter(returning_dates__gt=1)

    # Stats
    today = timezone.localdate()
    active_customers = Customer.objects.filter(arrival_time__date=today).count()
    new_customers_today = Customer.objects.filter(registration_date__date=today).count()
    returning_customers = Customer.objects.annotate(
        d=Count('orders__created_at__date', distinct=True)
    ).filter(d__gt=1).count()

    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    customers = paginator.get_page(page)
    return render(request, "tracker/customers_list.html", {
        "customers": customers,
        "q": q,
        "active_customers": active_customers,
        "new_customers_today": new_customers_today,
        "returning_customers": returning_customers,
    })


@login_required
def customers_search(request: HttpRequest):
    q = request.GET.get("q", "").strip()
    customer_id = request.GET.get("id")
    recent = request.GET.get("recent")
    details = request.GET.get("details")

    results = []

    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            results = [customer]
        except Customer.DoesNotExist:
            pass
    elif recent:
        results = Customer.objects.all().order_by('-last_visit', '-registration_date')[:10]
    elif q:
        results = Customer.objects.filter(
            Q(full_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q) |
            Q(code__icontains=q)
        ).order_by('-last_visit', '-registration_date')[:20]

    data = []
    for c in results:
        item = {
            "id": c.id,
            "code": c.code,
            "name": c.full_name,
            "phone": c.phone,
            "email": c.email or '',
            "type": c.customer_type or 'personal',
            "customer_type_display": c.get_customer_type_display() if c.customer_type else 'Personal',
            "last_visit": c.last_visit.isoformat() if c.last_visit else None,
            "total_visits": c.total_visits,
            "address": c.address or '',
        }
        if details and customer_id:
            item.update({
                "organization_name": c.organization_name or '',
                "tax_number": c.tax_number or '',
                "personal_subtype": c.personal_subtype or '',
                "current_status": c.current_status or '',
                "registration_date": c.registration_date.isoformat() if c.registration_date else None,
                "vehicles": [
                    {"id": v.id, "plate_number": v.plate_number, "make": v.make or '', "model": v.model or ''}
                    for v in c.vehicles.all()
                ],
                "orders": [
                    {"id": o.id, "order_number": o.order_number, "type": o.type, "status": o.status, "created_at": o.created_at.isoformat()}
                    for o in c.orders.order_by('-created_at')[:5]
                ],
            })
        data.append(item)
    return JsonResponse({"results": data})


@login_required
def customer_detail(request: HttpRequest, pk: int):
    c = get_object_or_404(Customer, pk=pk)
    vehicles = c.vehicles.all()
    orders = c.orders.order_by("-created_at")[:20]

    # Charts: last 6 months order trend and status distribution
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from calendar import month_abbr

    today = timezone.localdate().replace(day=1)
    months = []
    m_ptr = today
    for _ in range(6):
        months.append(m_ptr)
        # move back one month safely
        prev = (m_ptr - timezone.timedelta(days=1)).replace(day=1)
        m_ptr = prev
    months = list(reversed(months))

    month_counts_qs = (
        Order.objects.filter(customer=c)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(c=Count("id"))
    )
    month_map = {row["m"].date(): row["c"] for row in month_counts_qs if row["m"]}
    cd_trend = {
        "labels": [f"{month_abbr[m.month]} {m.year}" for m in months],
        "values": [month_map.get(m, 0) for m in months],
    }

    status_qs = (
        Order.objects.filter(customer=c)
        .values("status")
        .annotate(c=Count("id"))
    )
    status_labels = []
    status_values = []
    for row in status_qs:
        label = (row["status"] or "").replace("_", " ").title()
        status_labels.append(label or "Unknown")
        status_values.append(row["c"])
    cd_status = {"labels": status_labels, "values": status_values}

    return render(request, "tracker/customer_detail.html", {
        'customer': c,
        'vehicles': vehicles,
        'orders': orders,
        'page_title': c.full_name,
        'cd_trend': json.dumps(cd_trend),
        'cd_status': json.dumps(cd_status),
    })


@login_required
def add_customer_note(request: HttpRequest, pk: int):
    """Add or update a note on a customer's profile"""
    customer = get_object_or_404(Customer, pk=pk)
    note_id = request.POST.get('note_id')
    
    if request.method == 'POST':
        note_content = request.POST.get('note', '').strip()
        if note_content:
            try:
                if note_id:  # Update existing note
                    note = get_object_or_404(CustomerNote, id=note_id, customer=customer)
                    note.content = note_content
                    note.save()
                    action = 'updated'
                else:  # Create new note
                    note = CustomerNote.objects.create(
                        customer=customer,
                        content=note_content,
                        created_by=request.user
                    )
                    action = 'added'
                
                # Log the action
                add_audit_log(
                    user=request.user,
                    action_type=f'customer_note_{action}',
                    description=f'{action.capitalize()} a note for customer {customer.full_name}',
                    customer_id=customer.id,
                    note_id=note.id
                )
                
                messages.success(request, f'Note {action} successfully.')
            except Exception as e:
                messages.error(request, f'Error saving note: {str(e)}')
        else:
            messages.error(request, 'Note content cannot be empty.')
    
    # Redirect back to the customer detail page
    return redirect('tracker:customer_detail', pk=customer.id)


def delete_customer_note(request: HttpRequest, customer_id: int, note_id: int):
    """Delete a customer note"""
    if request.method == 'POST':
        try:
            note = get_object_or_404(CustomerNote, id=note_id, customer_id=customer_id)
            
            # Log the action before deletion
            add_audit_log(
                user=request.user,
                action_type='customer_note_deleted',
                description=f'Deleted a note for customer {note.customer.full_name}',
                customer_id=customer_id,
                note_id=note_id
            )
            
            note.delete()
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse(
                {'success': False, 'error': str(e)}, 
                status=400
            )
    
    return JsonResponse(
        {'success': False, 'error': 'Invalid request method'}, 
        status=405
    )


@login_required
def customer_register(request: HttpRequest):
    # Get the current step from POST or GET, default to 1
    step = int(request.POST.get("step", request.GET.get("step", 1)))
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    load_step = request.GET.get('load_step') == '1'  # Check if this is a step load request
    
    def get_form_errors(form):
        errors = {}
        for field in form:
            if field.errors:
                errors[field.name] = [str(error) for error in field.errors]
        return errors
    
    def get_template_context(step, form, **kwargs):
        # Get item-brand mapping for the form
        from django.db.models import F
        items = InventoryItem.objects.annotate(
            brand_name=F('brand__name')
        ).values('name', 'brand_name').distinct()
        
        item_brands = {}
        for item in items:
            if item['name'] and item['brand_name']:
                item_brands[item['name']] = item['brand_name']
        
        context = {
            'step': step,
            'form': form,
            'intent': request.session.get('reg_step2', {}).get('intent'),
            'step1': request.session.get('reg_step1', {}),
            'step2': request.session.get('reg_step2', {}),
            'step3': request.session.get('reg_step3', {}),
            'today': timezone.now().date(),
            'brands': Brand.objects.all(),
            'item_brands_json': json.dumps(item_brands),
            **kwargs
        }
        return context
    
    def render_form(step, form, **kwargs):
        context = get_template_context(step, form, **kwargs)
        return render(request, 'tracker/partials/customer_registration_form.html', context)
    
    def json_response(success, form=None, redirect_url=None, **kwargs):
        response_data = {
            'success': success,
            'redirect_url': redirect_url,
            **kwargs
        }
        
        if form is not None:
            if form.is_valid():
                response_data['form_html'] = render_form(step, form).content.decode('utf-8')
            else:
                response_data['errors'] = get_form_errors(form)
                response_data['form_html'] = render_form(step, form).content.decode('utf-8')
        
        return JsonResponse(response_data)
    
    # Handle GET request for loading a specific step via AJAX
    if request.method == 'GET' and is_ajax and load_step:
        form_class = {
            1: CustomerStep1Form,
            2: CustomerStep2Form,
            3: CustomerStep3Form,
            4: CustomerStep4Form
        }.get(step, CustomerStep1Form)
        
        # Initialize form with session data if available
        form_data = request.session.get(f'reg_step{step}', {})
        form = form_class(initial=form_data)
        
        # Render the form template
        form_html = render_to_string(
            'tracker/partials/customer_registration_form.html',
            {'form': form, 'step': step},
            request=request
        )
        
        return JsonResponse({
            'success': True,
            'form_html': form_html,
            'step': step
        })
    
    # Handle form submission
    if request.method == "POST":
        if step == 1:
            form = CustomerStep1Form(request.POST)
            action = request.POST.get("action")
            save_only = request.POST.get("save_only") == "1"
            
            if form.is_valid():
                data = form.cleaned_data
                full_name = data.get("full_name")
                phone = data.get("phone")
                
                if action == "save_customer" or save_only:
                    
                    # Normalize phone number (remove all non-digit characters)
                    import re
                    normalized_phone = re.sub(r'\D', '', phone) if phone else ''
                    
                    # Check for existing customers with similar name and phone
                    existing_customers = Customer.objects.filter(
                        full_name__iexact=full_name
                    )
                    
                    # Check each potential match for phone number similarity
                    for customer in existing_customers:
                        # Normalize stored phone number for comparison
                        stored_phone = re.sub(r'\D', '', str(customer.phone or ''))
                        # Check for exact or partial match (at least 6 digits matching)
                        if len(normalized_phone) >= 6 and len(stored_phone) >= 6:
                            if normalized_phone in stored_phone or stored_phone in normalized_phone:
                                if is_ajax:
                                    return json_response(
                                        False, 
                                        form=form, 
                                        message=f'Customer already exists: {customer.full_name} ({customer.phone})',
                                        message_type='warning',
                                        redirect_url=reverse("tracker:customer_detail", kwargs={'pk': customer.id})
                                    )
                                messages.warning(request, f'Customer already exists: {customer.full_name} ({customer.phone})')
                                return redirect("tracker:customer_detail", pk=customer.id)
                    
                        # If quick save, create the customer immediately
                    c = Customer.objects.create(
                        full_name=full_name,
                        phone=phone,
                        email=data.get("email"),
                        address=data.get("address"),
                        notes=data.get("notes"),
                        customer_type=data.get("customer_type"),
                        organization_name=data.get("organization_name"),
                        tax_number=data.get("tax_number"),
                        personal_subtype=data.get("personal_subtype"),
                    )
                    
                    # Clear session data after saving
                    if 'reg_step1' in request.session:
                        del request.session['reg_step1']
                    
                    if is_ajax:
                        return json_response(
                            True,
                            message="Customer saved successfully",
                            message_type="success",
                            redirect_url=reverse("tracker:customer_detail", kwargs={'pk': c.id})
                        )
                    
                    messages.success(request, "Customer saved successfully")
                    return redirect("tracker:customer_detail", pk=c.id)
                
                # Continue to next step
                request.session["reg_step1"] = form.cleaned_data
                request.session.save()
                
                if is_ajax:
                    return json_response(True, form=form)
                    
                return redirect(f"{reverse('tracker:customer_register')}?step=2")
            else:
                if is_ajax:
                    return json_response(False, form=form)
        
        elif step == 2:
            form = CustomerStep2Form(request.POST)
            if form.is_valid():
                request.session["reg_step2"] = form.cleaned_data
                request.session.save()
                intent = form.cleaned_data.get("intent")
                # If inquiry, skip service type selection and go to step 4
                next_step = 4 if intent == "inquiry" else 3
                
                if is_ajax:
                    return json_response(True, form=form)
                    
                return redirect(f"{reverse('tracker:customer_register')}?step={next_step}")
            elif is_ajax:
                return json_response(False, form=form)
                
        elif step == 3:
            form = CustomerStep3Form(request.POST)
            if form.is_valid():
                request.session["reg_step3"] = form.cleaned_data
                request.session.save()
                
                if is_ajax:
                    return json_response(True, form=form)
                    
                return redirect(f"{reverse('tracker:customer_register')}?step=4")
            elif is_ajax:
                return json_response(False, form=form)
                
        elif step == 4:
            form = CustomerStep4Form(request.POST)
            if form.is_valid():
                # Get all session data
                step1_data = request.session.get("reg_step1", {})
                step2_data = request.session.get("reg_step2", {})
                step3_data = request.session.get("reg_step3", {})
                
                # Validate that we have required data
                if not step1_data.get("full_name"):
                    if is_ajax:
                        return json_response(
                            False,
                            form=form,
                            message="Missing customer information. Please start from Step 1.",
                            message_type="error",
                            redirect_url=f"{reverse('tracker:customer_register')}?step=1"
                        )
                    messages.error(request, "Missing customer information. Please start from Step 1.")
                    return redirect(f"{reverse('tracker:customer_register')}?step=1")
                
                # Check for existing customer with same name and phone
                data = {**step1_data, **form.cleaned_data}
                full_name = data.get("full_name")
                phone = data.get("phone")
                
                # Check for existing customer
                existing_customer = Customer.objects.filter(
                    full_name__iexact=full_name,
                    phone=phone
                ).first()
                
                if existing_customer:
                    if is_ajax:
                        return json_response(
                            False,
                            form=form,
                            message=f"Customer '{full_name}' with phone '{phone}' already exists. You've been redirected to their profile.",
                            message_type="info",
                            redirect_url=reverse("tracker:customer_detail", kwargs={'pk': existing_customer.id})
                        )
                    messages.info(request, f"Customer '{full_name}' with phone '{phone}' already exists. You've been redirected to their profile.")
                    return redirect("tracker:customer_detail", pk=existing_customer.id)
                
                # Create new customer if no duplicate found
                c = Customer.objects.create(
                    full_name=full_name,
                    phone=phone,
                    email=data.get("email"),
                    address=data.get("address"),
                    notes=data.get("notes") or data.get("additional_notes"),
                    customer_type=data.get("customer_type"),
                    organization_name=data.get("organization_name"),
                    tax_number=data.get("tax_number"),
                    personal_subtype=data.get("personal_subtype"),
                )
                
                # Create vehicle if car service was selected
                v = None
                intent = step2_data.get("intent")
                service_type = step3_data.get("service_type")
                
                if intent == "service" and service_type == "car_service":
                    plate_number = request.POST.get("plate_number")
                    make = request.POST.get("make")
                    model = request.POST.get("model")
                    vehicle_type = request.POST.get("vehicle_type")
                    
                    if plate_number or make or model:
                        v = Vehicle.objects.create(
                            customer=c,
                            plate_number=plate_number,
                            make=make,
                            model=model,
                            vehicle_type=vehicle_type
                        )
                
                # Create order based on intent and service type
                o = None
                if intent == "service" and service_type == "tire_sales":
                    # Tire sales order
                    item_name = request.POST.get("item_name")
                    brand_input = (request.POST.get("brand") or '').strip()
                    quantity = request.POST.get("quantity")
                    tire_type = request.POST.get("tire_type")
                    # Optional tire service add-ons
                    tire_services = request.POST.getlist("tire_services") or []

                    if item_name and brand_input and quantity:
                        # Check inventory
                        inv_check_ok = True
                        qty_int = int(quantity)

                        # Resolve brand by id or name (case-insensitive)
                        if brand_input.isdigit():
                            brand_obj = Brand.objects.filter(id=int(brand_input)).first()
                        else:
                            brand_obj = Brand.objects.filter(name__iexact=brand_input).first()
                        
                        if not brand_obj and is_ajax:
                            return json_response(
                                False,
                                form=form,
                                message=f'Brand "{brand_input}" not found',
                                message_type='error'
                            )
                        
                        if not brand_obj:
                            messages.error(request, f'Brand "{brand_input}" not found')
                            inv_check_ok = False
                        else:
                            # Now filter by brand object
                            item = InventoryItem.objects.filter(name=item_name, brand=brand_obj).first()
                            if not item:
                                if is_ajax:
                                    return json_response(
                                        False,
                                        form=form,
                                        message=f'Item "{item_name}" not found for brand "{brand_obj.name}" in inventory',
                                        message_type='error'
                                    )
                                messages.error(request, f'Item "{item_name}" not found for brand "{brand_obj.name}" in inventory')
                                inv_check_ok = False
                            elif item.quantity < qty_int:
                                if is_ajax:
                                    return json_response(
                                        False,
                                        form=form,
                                        message=f'Only {item.quantity} in stock for {item_name} ({brand_obj.name})',
                                        message_type='error'
                                    )
                                messages.error(request, f'Only {item.quantity} in stock for {item_name} ({brand_obj.name})')
                                inv_check_ok = False

                        if not inv_check_ok:
                            if is_ajax:
                                return json_response(False, form=form)
                            context = {"step": 4, "form": form}
                            context.update({"step1": step1_data, "step2": step2_data, "step3": step3_data})
                            return render(request, "tracker/customer_register.html", context)

                        desc_addons = (", addons: " + ", ".join(tire_services)) if tire_services else ""
                        o = Order.objects.create(
                            customer=c,
                            vehicle=v,
                            type="sales",
                            item_name=item_name,
                            brand=brand_obj.name,
                            quantity=qty_int,
                            tire_type=tire_type,
                            status="created",
                            description=f"Tire Sales: {item_name} ({brand_obj.name}) - {tire_type}{desc_addons}"
                        )

                        # Adjust inventory
                        from .utils import adjust_inventory
                        adjust_inventory(item_name, brand_obj.name, -qty_int)
                        
                elif intent == "service" and service_type == "car_service":
                    # Car service order
                    # Persist selected service checkboxes from order_form (if any)
                    selected_svcs = request.POST.getlist('service_selection') or []
                    desc_svcs = (", services: " + ", ".join(selected_svcs)) if selected_svcs else ""
                    o = Order.objects.create(
                        customer=c,
                        vehicle=v,
                        type="service",
                        status="created",
                        description=f"Car Service{desc_svcs}"
                    )
                    
                elif intent == "inquiry":
                    # Inquiry order
                    inquiry_type = request.POST.get("inquiry_type")
                    questions = request.POST.get("questions")
                    contact_preference = request.POST.get("contact_preference")
                    followup_date = request.POST.get("followup_date")
                    
                    o = Order.objects.create(
                        customer=c,
                        vehicle=v,
                        type="consultation",
                        status="created",
                        description=f"Inquiry: {inquiry_type} - {questions}",
                        inquiry_type=inquiry_type,
                        questions=questions,
                        contact_preference=contact_preference,
                        follow_up_date=followup_date if followup_date else None
                    )
                
                # Clear session data
                for key in ["reg_step1", "reg_step2", "reg_step3"]:
                    request.session.pop(key, None)
                
                if is_ajax:
                    return json_response(
                        True,
                        message="Customer registered and order created successfully",
                        message_type="success",
                        redirect_url=reverse("tracker:customer_detail", kwargs={'pk': c.id})
                    )
                    
                messages.success(request, "Customer registered and order created successfully")
                return redirect("tracker:customer_detail", pk=c.id)
            elif is_ajax:
                return json_response(False, form=form)
        
        if is_ajax:
            return json_response(False, form=form)
    
    # Handle GET requests or load_step AJAX requests
    if is_ajax and request.method == 'GET' and 'load_step' in request.GET:
        # Return just the form HTML for AJAX requests
        if step == 1:
            form = CustomerStep1Form(initial=request.session.get("reg_step1"))
        elif step == 2:
            form = CustomerStep2Form(initial=request.session.get("reg_step2"))
        elif step == 3:
            form = CustomerStep3Form(initial=request.session.get("reg_step3"))
        else:
            form = CustomerStep4Form()
        
        return json_response(True, form=form)
    
    # For non-AJAX GET requests, render the full page
    context = {"step": step}
    # Read previously selected intent for conditional rendering
    session_step2 = request.session.get("reg_step2", {}) or {}
    intent = session_step2.get("intent")
    context["intent"] = intent
    
    # Include previous steps for all steps (for conditional rendering)
    context["step1"] = request.session.get("reg_step1", {})
    context["step2"] = session_step2
    context["step3"] = request.session.get("reg_step3", {})
    context["today"] = timezone.now().date()
    context["brands"] = Brand.objects.all()
    
    if step == 1:
        context["form"] = CustomerStep1Form(initial=request.session.get("reg_step1"))
    elif step == 2:
        context["form"] = CustomerStep2Form(initial=session_step2)
    elif step == 3:
        context["form"] = CustomerStep3Form(initial=request.session.get("reg_step3"))
    else:
        context["form"] = CustomerStep4Form()
        context["vehicle_form"] = VehicleForm()
        # Prefill order type based on intent and selected services
        type_map = {"service": "service", "sales": "sales", "inquiry": "consultation"}
        order_initial = {"type": type_map.get(intent)} if intent in type_map else {}
        sel_services = context["step3"].get("service_type") or []
        if sel_services:
            order_initial["service_selection"] = sel_services
        context["order_form"] = OrderForm(initial=order_initial)
    
    if is_ajax:
        # This shouldn't normally be reached, but just in case
        return json_response(True, **context)
    
    return render(request, "tracker/customer_register.html", context)


@login_required
def start_order(request: HttpRequest):
    """Start a new order by selecting a customer"""
    customers = Customer.objects.all().order_by('full_name')
    return render(request, 'tracker/select_customer.html', {
        'customers': customers,
        'page_title': 'Select Customer for New Order'
    })


@login_required
def create_order_for_customer(request: HttpRequest, pk: int):
    """Create a new order for a specific customer"""
    from .utils import adjust_inventory
    c = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = OrderForm(request.POST)
        # Ensure vehicle belongs to this customer
        form.fields["vehicle"].queryset = c.vehicles.all()
        if form.is_valid():
            o = form.save(commit=False)
            o.customer = c
            o.status = "created"
            # Inventory check for sales
            if o.type == 'sales':
                name = (o.item_name or '').strip()
                brand = (o.brand or '').strip()
                qty = int(o.quantity or 0)
                from django.db.models import Sum
                available = InventoryItem.objects.filter(name=name, brand__name__iexact=brand).aggregate(total=Sum('quantity')).get('total') or 0
                if not name or not brand or qty <= 0:
                    messages.error(request, 'Item, brand and valid quantity are required')
                    return render(request, "tracker/order_create.html", {"customer": c, "form": form})
                if available < qty:
                    messages.error(request, f'Only {available} in stock for {name} ({brand})')
                    return render(request, "tracker/order_create.html", {"customer": c, "form": form})
            o.save()
            # Deduct inventory after save
            if o.type == 'sales':
                qty_int = int(o.quantity or 0)
                ok, _, remaining = adjust_inventory(o.item_name, o.brand, -qty_int)
                if ok:
                    messages.success(request, f"Order created. Remaining stock for {o.item_name} ({o.brand}): {remaining}")
                else:
                    messages.warning(request, 'Order created, but inventory not adjusted')
            else:
                messages.success(request, "Order created successfully")
            return redirect("tracker:order_detail", pk=o.id)
        else:
            messages.error(request, "Please fix form errors and try again")
    else:
        form = OrderForm()
        form.fields["vehicle"].queryset = c.vehicles.all()
    return render(request, "tracker/order_create.html", {"customer": c, "form": form})


@login_required
def customer_groups(request: HttpRequest):
    """Advanced customer groups page with detailed analytics and insights"""
    from django.db.models import Count, Sum, Avg, Max, Min, Q, F
    from django.db.models.functions import TruncMonth, TruncWeek
    from datetime import datetime, timedelta
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return customer_groups_data(request)
        
    # Optional server-side chart generation (matplotlib may be unavailable in some envs)
    try:
        from tracker.utils.chart_utils import generate_monthly_trend_chart
    except Exception:
        generate_monthly_trend_chart = None
    
    # Get filter parameters
    selected_group = request.GET.get('group', 'all')
    time_period = request.GET.get('period', '6months')
    sort_by = request.GET.get('sort')
    
    # Set default sort if not provided or empty
    if not sort_by:
        sort_by = 'total_spent'
    
    # Validate sort field
    valid_sort_fields = [
        'total_spent', 'recent_orders_count', 'last_order_date', 'first_order_date',
        'service_orders', 'sales_orders', 'consultation_orders', 'completed_orders',
        'cancelled_orders', 'vehicles_count'
    ]
    
    # Extract field name and direction
    sort_field = sort_by.lstrip('-')
    sort_direction = '-' if sort_by.startswith('-') else ''
    
    # Validate sort field
    if sort_field not in valid_sort_fields:
        sort_field = 'total_spent'
        sort_direction = '-'
    
    sort_by = f"{sort_direction}{sort_field}"
    
    # Calculate time range
    today = timezone.now().date()
    if time_period == '1month':
        start_date = today - timedelta(days=30)
    elif time_period == '3months':
        start_date = today - timedelta(days=90)
    elif time_period == '6months':
        start_date = today - timedelta(days=180)
    elif time_period == '1year':
        start_date = today - timedelta(days=365)
    else:
        start_date = today - timedelta(days=180)  # default
    
    # Base customer queryset with annotations
    customers_base = Customer.objects.annotate(
        recent_orders_count=Count('orders', filter=Q(orders__created_at__date__gte=start_date)),
        last_order_date=Max('orders__created_at'),
        first_order_date=Min('orders__created_at'),
        service_orders=Count('orders', filter=Q(orders__type='service', orders__created_at__date__gte=start_date)),
        sales_orders=Count('orders', filter=Q(orders__type='sales', orders__created_at__date__gte=start_date)),
        consultation_orders=Count('orders', filter=Q(orders__type='consultation', orders__created_at__date__gte=start_date)),
        completed_orders=Count('orders', filter=Q(orders__status='completed', orders__created_at__date__gte=start_date)),
        cancelled_orders=Count('orders', filter=Q(orders__status='cancelled', orders__created_at__date__gte=start_date)),
        vehicles_count=Count('vehicles', distinct=True)
    )
    
    # Get all defined customer types from the model
    all_customer_types = dict(Customer.TYPE_CHOICES)
    
    # Calculate total customers (all customers in the system)
    total_customers = Customer.objects.count()
    
    # Calculate active customers this month (customers with orders in the last 30 days)
    one_month_ago = timezone.now() - timedelta(days=30)
    active_customers_this_month = Customer.objects.filter(
        orders__created_at__gte=one_month_ago
    ).distinct().count()
    
    # Customer type groups with detailed analytics
    customer_groups = {}
    
    # Get customer counts per group for current period
    current_period_counts = dict(Customer.objects.values_list('customer_type').annotate(
        count=Count('id')
    ).values_list('customer_type', 'count'))
    
    # Get customer counts for previous period for growth calculation
    prev_period_start = start_date - (today - start_date)  # Same length as current period
    prev_period_counts = dict(Customer.objects.filter(
        registration_date__lt=start_date,
        registration_date__gte=prev_period_start
    ).values_list('customer_type').annotate(
        count=Count('id')
    ).values_list('customer_type', 'count'))
    
    # Process each customer type
    for customer_type, display_name in all_customer_types.items():
        # Get customers for this group in current period
        group_customers = customers_base.filter(customer_type=customer_type)
        group_customer_count = current_period_counts.get(customer_type, 0)
        
        # Calculate growth percentage
        prev_count = prev_period_counts.get(customer_type, 0)
        growth_percent = 0
        if prev_count > 0:
            growth_percent = round(((group_customer_count - prev_count) / prev_count) * 100, 1)
        elif group_customer_count > 0:
            growth_percent = 100  # If no previous customers but have current, show 100% growth
            
        # Initialize default values for groups with no customers
        group_stats = {
            'total_revenue': 0,
            'avg_revenue_per_customer': 0,
            'total_orders': 0,
            'avg_orders_per_customer': 0,
            'avg_order_value': 0,
            'total_service_orders': 0,
            'total_sales_orders': 0,
            'total_consultation_orders': 0,
            'total_completed_orders': 0,
            'total_cancelled_orders': 0,
            'total_vehicles': 0,
        }
        
        # If group has customers, get their stats
        if group_customer_count > 0:
            group_stats = group_customers.aggregate(
                total_revenue=Sum('total_spent') or 0,
                total_orders=Sum('recent_orders_count') or 0,
                total_service_orders=Sum('service_orders') or 0,
                total_sales_orders=Sum('sales_orders') or 0,
                total_consultation_orders=Sum('consultation_orders') or 0,
                total_completed_orders=Sum('completed_orders') or 0,
                total_cancelled_orders=Sum('cancelled_orders') or 0,
                total_vehicles=Sum('vehicles_count') or 0,
            )
            
            # Calculate averages
            group_stats['avg_revenue_per_customer'] = (
                group_stats['total_revenue'] / group_customer_count 
                if group_customer_count > 0 else 0
            )
            group_stats['avg_orders_per_customer'] = (
                group_stats['total_orders'] / group_customer_count 
                if group_customer_count > 0 else 0
            )
            group_stats['avg_order_value'] = (
                group_stats['total_revenue'] / group_stats['total_orders'] 
                if group_stats['total_orders'] > 0 else 0
            )
        
        # Only calculate metrics if there are customers
        if total_customers > 0:
            group_stats = group_customers.aggregate(
                total_revenue=Sum('total_spent') or 0,
                avg_revenue_per_customer=Avg('total_spent') or 0,
                total_orders=Sum('recent_orders_count') or 0,
                avg_orders_per_customer=Avg('recent_orders_count') or 0,
                avg_order_value=Avg('total_spent') or 0,
                total_service_orders=Sum('service_orders') or 0,
                total_sales_orders=Sum('sales_orders') or 0,
                total_consultation_orders=Sum('consultation_orders') or 0,
                total_completed_orders=Sum('completed_orders') or 0,
                total_cancelled_orders=Sum('cancelled_orders') or 0,
                total_vehicles=Sum('vehicles_count') or 0,
            )
        
        # Customer segmentation within group
        high_value = group_customers.filter(total_spent__gte=1000).count()
        medium_value = group_customers.filter(total_spent__gte=500, total_spent__lt=1000).count()
        low_value = group_customers.filter(total_spent__lt=500).count()
        
        # Activity levels
        very_active = group_customers.filter(recent_orders_count__gte=5).count()
        active = group_customers.filter(recent_orders_count__gte=2, recent_orders_count__lt=5).count()
        inactive = group_customers.filter(recent_orders_count__lt=2).count()
        
        # Service preferences
        service_preference = group_customers.filter(service_orders__gt=F('sales_orders')).count()
        sales_preference = group_customers.filter(sales_orders__gt=F('service_orders')).count()
        mixed_preference = total_customers - service_preference - sales_preference if total_customers > 0 else 0
        
        # Recent activity trends
        recent_new_customers = group_customers.filter(registration_date__date__gte=start_date).count()
        returning_customers = group_customers.filter(total_visits__gt=1).count()
        
        # Calculate completion rate (completed orders / (completed + cancelled))
        completed = group_stats.get('total_completed_orders', 0) or 0
        cancelled = group_stats.get('total_cancelled_orders', 0) or 0
        total_orders_for_completion = completed + cancelled
        completion_rate = (completed / total_orders_for_completion * 100) if total_orders_for_completion > 0 else 0
        
        # Get top customers in this group (up to 5)
        top_customers = list(group_customers.order_by('-total_spent')[:5])
        
        # Add group to results
        customer_groups[customer_type] = {
            'name': display_name,
            'code': customer_type,
            'total_customers': group_customer_count,
            'growth_percent': growth_percent,
            'stats': group_stats,
            'segmentation': {
                'high_value': high_value,
                'medium_value': medium_value,
                'low_value': low_value,
            },
            'activity_levels': {
                'very_active': very_active,
                'active': active,
                'inactive': inactive,
            },
            'service_preferences': {
                'service_preference': service_preference,
                'sales_preference': sales_preference,
                'mixed_preference': mixed_preference,
            },
            'trends': {
                'recent_new_customers': recent_new_customers,
                'returning_customers': returning_customers,
                'completion_rate': round(completion_rate, 1) if group_customer_count > 0 else 0,
            },
            'top_customers': top_customers,
        }
    
    # Overall statistics - use base queryset without any filters for accurate totals
    overall_stats = {
        'total_revenue': customers_base.aggregate(total=Sum('total_spent'))['total'] or 0,
        'total_orders': customers_base.aggregate(total=Count('orders'))['total'] or 0,
    }
    
    # Calculate growth for overall metrics
    prev_period_stats = Customer.objects.filter(
        registration_date__lt=start_date,
        registration_date__gte=prev_period_start
    ).aggregate(
        total_revenue=Sum('total_spent', default=0),
        total_orders=Count('orders'),
        total_customers=Count('id')
    )
    
    # Calculate growth percentages
    overall_stats['revenue_growth'] = 0
    if prev_period_stats['total_revenue'] and prev_period_stats['total_revenue'] > 0:
        overall_stats['revenue_growth'] = round(
            ((overall_stats['total_revenue'] - prev_period_stats['total_revenue']) / 
             prev_period_stats['total_revenue']) * 100, 1
        )
        
    overall_stats['orders_growth'] = 0
    if prev_period_stats['total_orders'] > 0:
        overall_stats['orders_growth'] = round(
            ((overall_stats['total_orders'] - prev_period_stats['total_orders']) / 
             prev_period_stats['total_orders']) * 100, 1
        )
    
    # Calculate averages safely to avoid division by zero
    overall_stats['avg_revenue_per_customer'] = (
        overall_stats['total_revenue'] / total_customers 
        if total_customers > 0 else 0
    )
    overall_stats['avg_orders_per_customer'] = (
        overall_stats['total_orders'] / total_customers 
        if total_customers > 0 else 0
    )
    
    # Get detailed customer list for selected group
    detailed_customers = []
    selected_group_display = ''
    if selected_group != 'all' and selected_group in dict(Customer.TYPE_CHOICES):
        detailed_customers = customers_base.filter(customer_type=selected_group).order_by(sort_by)[:50]
        selected_group_display = dict(Customer.TYPE_CHOICES).get(selected_group, selected_group)
    
    # Monthly trends for charts
    monthly_trends = {}
    monthly_charts = {}
    monthly_chart_data = {}
    
    for customer_type, display_name in Customer.TYPE_CHOICES:
        # Get monthly order data
        monthly_data = (Order.objects
                       .filter(customer__customer_type=customer_type, created_at__date__gte=start_date)
                       .annotate(month=TruncMonth('created_at'))
                       .values('month')
                       .annotate(
                           orders=Count('id'),
                           customers=Count('customer', distinct=True)
                       )
                       .order_by('month'))
        
        # Convert QuerySet to list of dicts for the template
        monthly_data_list = list(monthly_data)
        
        # Store the raw data
        monthly_trends[customer_type] = {
            'name': display_name,
            'data': monthly_data_list
        }
        
        # Prepare light payload for client-side chart (labels + series)
        if monthly_data_list:
            labels = [d['month'].strftime('%b %Y') if hasattr(d['month'], 'strftime') else str(d['month']) for d in monthly_data_list]
            series = [int(d.get('orders') or 0) for d in monthly_data_list]
            monthly_chart_data[customer_type] = {'labels': labels, 'series': series, 'title': f"{display_name} - Monthly Order Trends"}
        
        # Generate the chart image (if generator available)
        if monthly_data_list and callable(generate_monthly_trend_chart):
            chart_title = f"{display_name} - Monthly Order Trends"
            chart_image = generate_monthly_trend_chart(
                monthly_data_list,
                title=chart_title
            )
            monthly_charts[customer_type] = chart_image
    
    # Initialize variables with default values if not defined
    total_revenue = getattr(customers_base.aggregate(total=Sum('total_spent')), 'total', 0) or 0
    total_orders = getattr(customers_base.aggregate(total=Count('orders')), 'total', 0) or 0
    
    # Calculate growth percentages with proper default values
    revenue_growth = 0
    orders_growth = 0
    customers_growth = 0
    
    # Prepare context for the template
    context = {
        'customer_groups': customer_groups,
        'selected_group': selected_group,
        'time_period': time_period,
        'sort_by': sort_by,
        'selected_group_display': selected_group_display,
        'detailed_customers': detailed_customers,
        'total_customers': total_customers or 0,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'revenue_growth': revenue_growth,
        'orders_growth': orders_growth,
        'customers_growth': customers_growth,
        'chart_image': chart_image if 'chart_image' in locals() else None,
    }
    
    # If it's an AJAX request, return JSON response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.core import serializers
        
        # Convert the context to a JSON-serializable format
        response_data = {
            'customer_groups': customer_groups,
            'total_customers': total_customers,
            'total_revenue': float(total_revenue) if total_revenue else 0,
            'total_orders': total_orders,
            'revenue_growth': float(revenue_growth) if revenue_growth else 0,
            'orders_growth': float(orders_growth) if orders_growth else 0,
            'customers_growth': float(customers_growth) if customers_growth else 0,
        }
        return JsonResponse(response_data)
    
    # Define active groups (groups with customers)
    active_groups = [group for group, data in customer_groups.items() if data['total_customers'] > 0]
    
    # For regular requests, render the full template
    context = {
        'customer_groups': customer_groups,
        'overall_stats': overall_stats,
        'selected_group': selected_group,
        'selected_group_display': selected_group_display,
        'time_period': time_period,
        'sort_by': sort_by,
        'detailed_customers': detailed_customers,
        'monthly_trends': monthly_trends,
        'monthly_charts': monthly_charts,
        'monthly_chart_data': json.dumps(monthly_chart_data),  # Client-side chart payload
        'customer_type_choices': Customer.TYPE_CHOICES,
        'start_date': start_date,
        'end_date': today,
        'total_customers': total_customers,
        'active_customers_this_month': active_customers_this_month,
        'active_groups': active_groups,  # List of group codes with customers
    }
    
    # For regular requests, render the full template
    return render(request, 'tracker/customer_groups.html', context)


@login_required
def customer_groups_data(request: HttpRequest):
    """API endpoint for AJAX requests to get customer groups data"""
    from django.db.models import Count, Sum, Avg, Q, F
    from datetime import datetime, timedelta
    
    # Get filter parameters
    selected_group = request.GET.get('group', 'all')
    time_period = request.GET.get('period', '6months')
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    
    # Calculate date ranges based on time period
    end_date = datetime.now()
    if time_period == 'week':
        start_date = end_date - timedelta(days=7)
    elif time_period == 'month':
        start_date = end_date - timedelta(days=30)
    elif time_period == '3months':
        start_date = end_date - timedelta(days=90)
    elif time_period == '6months':
        start_date = end_date - timedelta(days=180)
    elif time_period == 'year':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = datetime(2000, 1, 1)  # All time
    
    # Base query for customers
    customers = Customer.objects.all()
    
    # Apply search filter
    if search_value:
        customers = customers.filter(
            Q(first_name__icontains=search_value) |
            Q(last_name__icontains=search_value) |
            Q(phone__icontains=search_value) |
            Q(email__icontains=search_value)
        )
    
    # Apply group filter
    if selected_group and selected_group != 'all':
        if selected_group == 'high_value':
            customers = customers.annotate(
                order_count=Count('orders')
            ).filter(
                order_count__gt=0,
                total_spent__gt=1000  # Example threshold for high-value
            )
        elif selected_group == 'inactive':
            customers = customers.filter(
                last_order_date__lt=end_date - timedelta(days=180)
            )
        # Add more group filters as needed
    
    # Get total count before pagination
    total_records = customers.count()
    
    # Apply pagination
    customers = customers[start:start + length]
    
    # Prepare data for DataTables
    data = []
    for customer in customers:
        data.append({
            'id': customer.id,
            'full_name': f"{customer.first_name} {customer.last_name}",
            'phone': customer.phone,
            'email': customer.email,
            'total_spent': float(customer.total_spent) if customer.total_spent else 0,
            'recent_orders_count': customer.orders.count(),
            'last_order_date': customer.last_order_date.strftime('%Y-%m-%d') if customer.last_order_date else 'N/A',
            'actions': f'''
                <a href="/customer/{customer.id}/" class="btn btn-sm btn-primary">
                    <i class="fas fa-eye"></i> View
                </a>
                <a href="/customer/{customer.id}/edit/" class="btn btn-sm btn-secondary">
                    <i class="fas fa-edit"></i> Edit
                </a>
            '''
        })
    
    # Prepare response
    response = {
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data,
    }
    
    return JsonResponse(response)

@login_required
def orders_list(request: HttpRequest):
    from django.db.models import Q, Sum
    
    # Get timezone from cookie or use default
    tzname = request.COOKIES.get('django_timezone')
    
    status = request.GET.get("status", "all")
    type_filter = request.GET.get("type", "all")
    priority = request.GET.get("priority", "")
    date_range = request.GET.get("date_range", "")
    customer_id = request.GET.get("customer", "")

    orders = Order.objects.select_related("customer", "vehicle").order_by("-created_at")

    # Apply filters
    if status != "all":
        orders = orders.filter(status=status)
    if type_filter != "all":
        orders = orders.filter(type=type_filter)
    if priority:
        orders = orders.filter(priority=priority)
    if customer_id:
        orders = orders.filter(customer_id=customer_id)
    if date_range == "today":
        today = timezone.localdate()
        orders = orders.filter(created_at__date=today)
    elif date_range == "week":
        week_ago = timezone.now() - timedelta(days=7)
        orders = orders.filter(created_at__gte=week_ago)
    elif date_range == "month":
        month_ago = timezone.now() - timedelta(days=30)
        orders = orders.filter(created_at__gte=month_ago)

    # Get counts for stats
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="created").count()
    active_orders = Order.objects.filter(status__in=["assigned", "in_progress"]).count()
    completed_today = Order.objects.filter(status="completed", completed_at__date=timezone.localdate()).count()
    urgent_orders = Order.objects.filter(priority="urgent").count()
    revenue_today = 0

    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders = paginator.get_page(page)
    return render(request, "tracker/orders_list.html", {
        "orders": orders,
        "status": status,
        "type": type_filter,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "active_orders": active_orders,
        "completed_today": completed_today,
        "urgent_orders": urgent_orders,
        "revenue_today": revenue_today,
        "timezone": tzname or timezone.get_current_timezone_name(),
    })
    # Support GET ?customer=<id> to go straight into order form for that customer
    if request.method == 'GET':
        cust_id = request.GET.get('customer')
        if cust_id:
            c = get_object_or_404(Customer, pk=cust_id)
            form = OrderForm()
            form.fields['vehicle'].queryset = c.vehicles.all()
            return render(request, "tracker/order_create.html", {"customer": c, "form": form})
        form = OrderForm()
        try:
            form.fields['vehicle'].queryset = Vehicle.objects.none()
        except Exception:
            pass
        return render(request, "tracker/order_create.html", {"form": form})

    # Handle POST (AJAX or standard form submit)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        customer_id = request.POST.get('customer_id')
        if not customer_id:
            return JsonResponse({'success': False, 'message': 'Customer ID is required'})
        customer = get_object_or_404(Customer, id=customer_id)
        order_data = {
            'customer': customer,
            'type': request.POST.get('type'),
            'priority': request.POST.get('priority', 'medium'),
            'status': 'created',
            'description': request.POST.get('description', ''),
            'estimated_duration': request.POST.get('estimated_duration') or None,
            'item_name': (request.POST.get('item_name') or '').strip(),
            'brand': (request.POST.get('brand') or '').strip(),
            'quantity': None,
            'inquiry_type': (request.POST.get('inquiry_type') or '').strip(),
            'questions': request.POST.get('questions', ''),
            'contact_preference': (request.POST.get('contact_preference') or '').strip(),
            'follow_up_date': request.POST.get('follow_up_date') or None,
        }
        vehicle_id = request.POST.get('vehicle')
        if vehicle_id:
            vehicle = get_object_or_404(Vehicle, id=vehicle_id, customer=customer)
            order_data['vehicle'] = vehicle
        if order_data.get('type') == 'sales':
            name = (order_data.get('item_name') or '').strip()
            brand = (order_data.get('brand') or '').strip()
            try:
                qty = int(request.POST.get('quantity') or 0)
            except (TypeError, ValueError):
                qty = 0
            if not name or not brand or qty <= 0:
                return JsonResponse({'success': False, 'message': 'Item, brand and valid quantity are required', 'code': 'invalid'})
            from django.db.models import Sum
            available = InventoryItem.objects.filter(name=name, brand__name__iexact=brand).aggregate(total=Sum('quantity')).get('total') or 0
            if available <= 0:
                return JsonResponse({'success': False, 'message': 'Item not found in inventory', 'code': 'not_found'})
            if available < qty:
                return JsonResponse({'success': False, 'message': f'Only {available} in stock for {name} ({brand})', 'code': 'insufficient_stock', 'available': available})
            order_data['quantity'] = qty
        order = Order.objects.create(**order_data)
        remaining = None
        if order.type == 'sales':
            from .utils import adjust_inventory
            qty_int = int(order.quantity or 0)
            ok, status, rem = adjust_inventory(order.item_name, order.brand, -qty_int)
            remaining = rem if ok else None
        return JsonResponse({'success': True, 'message': 'Order created successfully', 'order_id': order.id, 'remaining': remaining})

    # Standard form submit (non-AJAX)
    customer_id = request.POST.get('customer_id') or request.GET.get('customer')
    if not customer_id:
        messages.error(request, 'Customer is required to create an order')
        return render(request, "tracker/order_create.html")
    c = get_object_or_404(Customer, pk=customer_id)
    form = OrderForm(request.POST)
    form.fields['vehicle'].queryset = c.vehicles.all()
    if form.is_valid():
        o = form.save(commit=False)
        o.customer = c
        o.status = 'created'
        # Sales inventory validation
        if o.type == 'sales':
            name = (o.item_name or '').strip()
            brand = (o.brand or '').strip()
            qty = int(o.quantity or 0)
            from django.db.models import Sum
            available = InventoryItem.objects.filter(name=name, brand__name__iexact=brand).aggregate(total=Sum('quantity')).get('total') or 0
            if not name or not brand or qty <= 0:
                messages.error(request, 'Item, brand and valid quantity are required')
                return render(request, "tracker/order_create.html", {"customer": c, "form": form})
            if available < qty:
                messages.error(request, f'Only {available} in stock for {name} ({brand})')
                return render(request, "tracker/order_create.html", {"customer": c, "form": form})
        o.save()
        if o.type == 'sales':
            from .utils import adjust_inventory
            qty_int = int(o.quantity or 0)
            ok, status, remaining = adjust_inventory(o.item_name, o.brand, -qty_int)
            if ok:
                messages.success(request, f"Order created. Remaining stock for {o.item_name} ({o.brand}): {remaining}")
            else:
                messages.warning(request, 'Order created, but inventory not adjusted')
        else:
            messages.success(request, 'Order created successfully')
        return redirect('tracker:order_detail', pk=o.id)
    messages.error(request, 'Please fix form errors and try again')
    return render(request, "tracker/order_create.html", {"customer": c, "form": form})


@login_required
def order_edit(request: HttpRequest, pk: int):
    """Edit an existing order"""
    order = get_object_or_404(Order, pk=pk)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save()
            messages.success(request, 'Order updated successfully.')
            return redirect('tracker:order_detail', pk=order.pk)
    else:
        form = OrderForm(instance=order)
    
    # Set the vehicle queryset to only include vehicles for this customer
    form.fields['vehicle'].queryset = order.customer.vehicles.all()
    
    return render(request, 'tracker/order_form.html', {
        'form': form,
        'order': order,
        'title': 'Edit Order',
        'customer': order.customer
    })


@login_required
def order_delete(request: HttpRequest, pk: int):
    """Delete an order"""
    order = get_object_or_404(Order, pk=pk)
    customer = order.customer
    
    if request.method == 'POST':
        try:
            # Log the deletion before actually deleting
            add_audit_log(
                request.user,
                'order_deleted',
                f'Deleted order {order.order_number} for customer {customer.full_name}',
                order_id=order.id,
                customer_id=customer.id
            )
        except Exception:
            pass
            
        order.delete()
        messages.success(request, f'Order {order.order_number} has been deleted.')
        
        # Redirect based on the 'next' parameter or to customer detail
        next_url = request.POST.get('next', None)
        if next_url:
            return redirect(next_url)
        return redirect('tracker:customer_detail', pk=customer.id)
    
    # If not a POST request, redirect to order detail
    return redirect('tracker:order_detail', pk=order.id)


@login_required
def customer_detail(request: HttpRequest, pk: int):
    customer = get_object_or_404(Customer, pk=pk)
    orders = customer.orders.all().order_by('-created_at')
    vehicles = customer.vehicles.all()
    notes = customer.notes_history.all().order_by('-created_at')
    
    # Get timezone from cookie or use default
    tzname = request.COOKIES.get('django_timezone')
    
    return render(request, "tracker/customer_detail.html", {
        'customer': customer,
        'orders': orders,
        'vehicles': vehicles,
        'notes': notes,
        'timezone': tzname or timezone.get_current_timezone_name(),
    })


@login_required
def order_detail(request: HttpRequest, pk: int):
    order = get_object_or_404(Order, pk=pk)
    # Get timezone from cookie or use default
    tzname = request.COOKIES.get('django_timezone')
    
    # Prepare context with timezone info
    context = {
        "order": order,
        "timezone": tzname or timezone.get_current_timezone_name()
    }
    return render(request, "tracker/order_detail.html", context)


@login_required
def update_order_status(request: HttpRequest, pk: int):
    o = get_object_or_404(Order, pk=pk)
    status = request.POST.get("status")
    now = timezone.now()
    if status in dict(Order.STATUS_CHOICES):
        o.status = status
        if status == "assigned":
            o.assigned_at = now
        elif status == "in_progress":
            o.started_at = now
        elif status == "completed":
            o.completed_at = now
            if o.started_at:
                o.actual_duration = int((now - o.started_at).total_seconds() // 60)
            c = o.customer
            c.total_spent = c.total_spent + 0  # integrate billing later
            c.last_visit = now
            c.current_status = "completed"
            c.save()
        elif status == "cancelled":
            o.cancelled_at = now
            # Restock on cancellation for sales orders
            if o.type == 'sales' and (o.quantity or 0) > 0 and o.item_name and o.brand:
                from .utils import adjust_inventory
                adjust_inventory(o.item_name, o.brand, (o.quantity or 0))
        o.save()
        try:
            add_audit_log(request.user, 'order_status_update', f"Order {o.order_number}: {o.status}")
        except Exception:
            pass
        messages.success(request, f"Order status updated to {status.replace('_',' ').title()}")
    else:
        messages.error(request, "Invalid status")
    return redirect("tracker:order_detail", pk=o.id)


@login_required
def analytics(request: HttpRequest):
    from datetime import timedelta
    period = request.GET.get('period', 'monthly')

    today = timezone.localdate()
    if period == 'daily':
        start_date = today
        end_date = today
        labels = [f"{i:02d}:00" for i in range(24)]
    elif period == 'weekly':
        start_date = today - timedelta(days=6)
        end_date = today
        labels = [(start_date + timedelta(days=i)).strftime('%a') for i in range(7)]
    elif period == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
        labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    else:  # monthly
        start_date = today - timedelta(days=29)
        end_date = today
        labels = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)]

    qs = Order.objects.filter(created_at__date__range=[start_date, end_date])
    status_counts = {row['status']: row['c'] for row in qs.values('status').annotate(c=Count('id'))}
    type_counts = {row['type']: row['c'] for row in qs.values('type').annotate(c=Count('id'))}
    priority_counts = {row['priority']: row['c'] for row in qs.values('priority').annotate(c=Count('id'))}

    # Trend by selected period
    if period == 'daily':
        from django.db.models.functions import ExtractHour
        trend_map = {int(row['h'] or 0): row['c'] for row in qs.annotate(h=ExtractHour('created_at')).values('h').annotate(c=Count('id'))}
        trend_values = [trend_map.get(h, 0) for h in range(24)]
        trend_labels = labels
    elif period == 'weekly':
        by_date = {row['day']: row['c'] for row in qs.annotate(day=TruncDate('created_at')).values('day').annotate(c=Count('id'))}
        trend_values = []
        for i in range(7):
            d = start_date + timezone.timedelta(days=i)
            trend_values.append(by_date.get(d, 0))
        trend_labels = labels
    elif period == 'yearly':
        from django.db.models.functions import ExtractMonth
        by_month = {int(row['m']): row['c'] for row in qs.annotate(m=ExtractMonth('created_at')).values('m').annotate(c=Count('id'))}
        trend_values = [by_month.get(i, 0) for i in range(1, 13)]
        trend_labels = labels
    else:  # monthly
        by_date = {row['day']: row['c'] for row in qs.annotate(day=TruncDate('created_at')).values('day').annotate(c=Count('id'))}
        trend_values = []
        for i in range(30):
            d = start_date + timezone.timedelta(days=i)
            trend_values.append(by_date.get(d, 0))
        trend_labels = labels

    charts = {
        'status': {
            'labels': ['Created','Assigned','In Progress','Completed','Cancelled'],
            'values': [
                status_counts.get('created',0),
                status_counts.get('assigned',0),
                status_counts.get('in_progress',0),
                status_counts.get('completed',0),
                status_counts.get('cancelled',0),
            ]
        },
        'type': {
            'labels': ['Service','Sales','Consultation'],
            'values': [
                type_counts.get('service',0),
                type_counts.get('sales',0),
                type_counts.get('consultation',0),
            ]
        },
        'priority': {
            'labels': ['Low','Medium','High','Urgent'],
            'values': [
                priority_counts.get('low',0),
                priority_counts.get('medium',0),
                priority_counts.get('high',0),
                priority_counts.get('urgent',0),
            ]
        },
        'trend': { 'labels': trend_labels, 'values': trend_values },
    }

    totals = {
        'total_orders': qs.count(),
        'completed': qs.filter(status='completed').count(),
        'in_progress': qs.filter(status__in=['created','assigned','in_progress']).count(),
        'customers': Customer.objects.filter(registration_date__date__range=[start_date, end_date]).count(),
    }

    return render(request, 'tracker/analytics.html', {
        'charts_json': json.dumps(charts),
        'totals': totals,
        'period': period,
        'export_from': start_date.isoformat(),
        'export_to': end_date.isoformat(),
    })


@login_required
def reports(request: HttpRequest):
    f_from = request.GET.get("from")
    f_to = request.GET.get("to")
    f_type = request.GET.get("type", "all")
    period = request.GET.get("period", "")
    # If no explicit range provided, derive from period
    today = timezone.localdate()
    if (not f_from or not f_to) and period:
        if period == 'daily':
            f_from = f_from or today.isoformat()
            f_to = f_to or today.isoformat()
        elif period == 'weekly':
            start = today - timezone.timedelta(days=6)
            f_from = f_from or start.isoformat()
            f_to = f_to or today.isoformat()
        elif period == 'yearly':
            start = today.replace(month=1, day=1)
            f_from = f_from or start.isoformat()
            f_to = f_to or today.isoformat()
        else:  # monthly default (last 30 days)
            start = today - timezone.timedelta(days=29)
            f_from = f_from or start.isoformat()
            f_to = f_to or today.isoformat()
    qs = Order.objects.select_related("customer").order_by("-created_at")
    if f_from:
        try:
            qs = qs.filter(created_at__date__gte=f_from)
        except Exception:
            pass
    if f_to:
        try:
            qs = qs.filter(created_at__date__lte=f_to)
        except Exception:
            pass
    if f_type and f_type != "all":
        qs = qs.filter(type=f_type)

    total = qs.count()
    by_status = dict(qs.values_list("status").annotate(c=Count("id")))
    # Completed orders should be from the same base queryset to ensure date range consistency
    completed_qs = qs.filter(status="completed")
    if f_from:
        try:
            completed_qs = completed_qs.filter(completed_at__date__gte=f_from)
        except Exception:
            pass
    if f_to:
        try:
            completed_qs = completed_qs.filter(completed_at__date__lte=f_to)
        except Exception:
            pass

    stats = {
        "total": total,
        "completed": completed_qs.filter(status="completed").count(),
        "in_progress": by_status.get("in_progress", 0) + by_status.get("assigned", 0) + by_status.get("created", 0),
        "cancelled": by_status.get("cancelled", 0),
    }

    # Charts (trend/status/type) for selected range
    from django.db.models.functions import TruncDate
    trend_map = {row['day']: row['c'] for row in qs.annotate(day=TruncDate('created_at')).values('day').annotate(c=Count('id'))}
    labels = []
    values = []
    if f_from and f_to:
        try:
            from datetime import date, timedelta
            start = date.fromisoformat(f_from)
            end = date.fromisoformat(f_to)
            days = (end - start).days
            for i in range(days + 1):
                d = start + timedelta(days=i)
                labels.append(d.isoformat())
                values.append(trend_map.get(d, 0))
        except Exception:
            pass
    if not labels:
        for d, c in sorted(trend_map.items()):
            labels.append(d.isoformat() if hasattr(d, 'isoformat') else str(d))
            values.append(c)

    type_counts = {row['type']: row['c'] for row in qs.values('type').annotate(c=Count('id'))}

    charts = {
        'status': {
            'labels': ['Created','Assigned','In Progress','Completed','Cancelled'],
            'values': [
                by_status.get('created',0),
                by_status.get('assigned',0),
                by_status.get('in_progress',0),
                by_status.get('completed',0),
                by_status.get('cancelled',0),
            ]
        },
        'type': {
            'labels': ['Service','Sales','Consultation'],
            'values': [
                type_counts.get('service',0),
                type_counts.get('sales',0),
                type_counts.get('consultation',0),
            ]
        },
        'trend': {'labels': labels, 'values': values},
    }

    orders = list(qs[:300])
    return render(
        request,
        "tracker/reports.html",
        {
            "orders": orders,
            "stats": stats,
            "filters": {"from": f_from, "to": f_to, "type": f_type},
            "charts_json": json.dumps(charts),
            "period": period or ("monthly" if not f_from and not f_to else "custom"),
            "export_from": f_from or (labels[0] if labels else ""),
            "export_to": f_to or (labels[-1] if labels else ""),
        },
    )

@login_required
def reports_export(request: HttpRequest):
    # Same filters as reports
    f_from = request.GET.get("from")
    f_to = request.GET.get("to")
    f_type = request.GET.get("type", "all")
    qs = Order.objects.select_related("customer").order_by("-created_at")
    if f_from:
        try:
            qs = qs.filter(created_at__date__gte=f_from)
        except Exception:
            pass
    if f_to:
        try:
            qs = qs.filter(created_at__date__lte=f_to)
        except Exception:
            pass
    if f_type and f_type != "all":
        qs = qs.filter(type=f_type)

    # Build CSV
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders_report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Order", "Customer", "Type", "Status", "Priority", "Created At"])
    for o in qs.iterator():
        writer.writerow([o.order_number, o.customer.full_name, o.type, o.status, o.priority, o.created_at.isoformat()])
    return response

@login_required
def customers_export(request: HttpRequest):
    q = request.GET.get('q','').strip()
    qs = Customer.objects.all().order_by('-registration_date')
    if q:
        qs = qs.filter(full_name__icontains=q)
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customers.csv"'
    writer = csv.writer(response)
    writer.writerow(['Code','Name','Phone','Type','Visits','Last Visit'])
    for c in qs.iterator():
        writer.writerow([c.code, c.full_name, c.phone, c.customer_type, c.total_visits, c.last_visit.isoformat() if c.last_visit else '' ])
    return response

@login_required
def orders_export(request: HttpRequest):
    status = request.GET.get('status','all')
    type_ = request.GET.get('type','all')
    qs = Order.objects.select_related('customer').order_by('-created_at')
    if status != 'all':
        qs = qs.filter(status=status)
    if type_ != 'all':
        qs = qs.filter(type=type_)
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders.csv"'
    writer = csv.writer(response)
    writer.writerow(["Order","Customer","Type","Status","Priority","Created At"])
    for o in qs.iterator():
        writer.writerow([o.order_number, o.customer.full_name, o.type, o.status, o.priority, o.created_at.isoformat()])
    return response

@login_required
def customer_groups_export(request: HttpRequest):
    """Export filtered customer group data to CSV"""
    from datetime import timedelta
    selected_group = request.GET.get('group', '')
    time_period = request.GET.get('period', '6months')
    today = timezone.now().date()
    if time_period == '1month':
        start_date = today - timedelta(days=30)
    elif time_period == '3months':
        start_date = today - timedelta(days=90)
    elif time_period == '6months':
        start_date = today - timedelta(days=180)
    elif time_period == '1year':
        start_date = today - timedelta(days=365)
    else:
        start_date = today - timedelta(days=180)

    qs = Customer.objects.annotate(
        recent_orders_count=Count('orders', filter=Q(orders__created_at__date__gte=start_date)),
        last_order_date=Max('orders__created_at'),
        service_orders=Count('orders', filter=Q(orders__type='service', orders__created_at__date__gte=start_date)),
        sales_orders=Count('orders', filter=Q(orders__type='sales', orders__created_at__date__gte=start_date)),
        consultation_orders=Count('orders', filter=Q(orders__type='consultation', orders__created_at__date__gte=start_date)),
        completed_orders=Count('orders', filter=Q(orders__status='completed', orders__created_at__date__gte=start_date)),
        vehicles_count=Count('vehicles', distinct=True),
    )
    if selected_group and selected_group in dict(Customer.TYPE_CHOICES):
        qs = qs.filter(customer_type=selected_group)
    import csv
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="customer_group.csv"'
    w = csv.writer(resp)
    w.writerow(['Code','Name','Phone','Type','Visits','Total Spent','Orders (period)','Service','Sales','Consultation','Completed (period)','Vehicles','Last Order'])
    for c in qs.iterator():
        w.writerow([
            c.code,
            c.full_name,
            c.phone,
            c.customer_type,
            c.total_visits,
            c.total_spent,
            c.recent_orders_count,
            c.service_orders,
            c.sales_orders,
            c.consultation_orders,
            c.completed_orders,
            c.vehicles_count,
            c.last_order_date.isoformat() if c.last_order_date else '',
        ])
    return resp

@login_required
def profile(request: HttpRequest):
    """Update current user's profile (name and photo)."""
    user = request.user
    
    # Get or create profile
    profile_obj, created = Profile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        form = ProfileForm(
            request.POST, 
            request.FILES, 
            instance=profile_obj,
            user=user
        )
        if form.is_valid():
            form.save(user)  # Pass the user to the save method
            messages.success(request, 'Profile updated successfully!')
            return redirect('tracker:profile')
        else:
            # Add form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        form = ProfileForm(instance=profile_obj, user=user)
    
    return render(request, 'tracker/profile.html', {
        'form': form,
        'profile': profile_obj,
        'user': user
    })

@login_required
def api_check_customer_duplicate(request: HttpRequest):
    full_name = (request.GET.get("full_name") or "").strip()
    phone = (request.GET.get("phone") or "").strip()
    customer_type = (request.GET.get("customer_type") or "").strip()
    org = (request.GET.get("organization_name") or "").strip()
    tax = (request.GET.get("tax_number") or "").strip()

    if not full_name or not phone:
        return JsonResponse({"exists": False})

    qs = Customer.objects.all()
    if customer_type == "personal":
        qs = qs.filter(full_name=full_name, phone=phone, customer_type="personal")
    elif customer_type in ["government", "ngo", "company"]:
        if not org or not tax:
            return JsonResponse({"exists": False})
        qs = qs.filter(
            full_name=full_name,
            phone=phone,
            organization_name=org,
            tax_number=tax,
            customer_type=customer_type,
        )
    else:
        qs = qs.filter(full_name=full_name, phone=phone)
        if org:
            qs = qs.filter(organization_name=org)
        if tax:
            qs = qs.filter(tax_number=tax)

    c = qs.first()
    if not c:
        return JsonResponse({"exists": False})

    data = {
        "id": c.id,
        "code": c.code,
        "full_name": c.full_name,
        "phone": c.phone,
        "email": c.email or "",
        "address": c.address or "",
        "customer_type": c.customer_type or "",
        "organization_name": c.organization_name or "",
        "tax_number": c.tax_number or "",
        "total_visits": c.total_visits,
        "last_visit": c.last_visit.isoformat() if c.last_visit else "",
        "detail_url": reverse("tracker:customer_detail", kwargs={"pk": c.id}),
        "create_order_url": reverse("tracker:create_order_for_customer", kwargs={"pk": c.id}),
    }
    return JsonResponse({"exists": True, "customer": data})


@login_required
def api_recent_orders(request: HttpRequest):
    recents = Order.objects.select_related("customer", "vehicle").exclude(status="completed").order_by("-created_at")[:10]
    data = [
        {
            "order_number": r.order_number,
            "status": r.status,
            "type": r.type,
            "priority": r.priority,
            "customer": r.customer.full_name,
            "vehicle": r.vehicle.plate_number if r.vehicle else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in recents
    ]
    return JsonResponse({"orders": data})

@login_required
def api_inventory_items(request: HttpRequest):
    """API endpoint to get all inventory items with their brands"""
    from django.db.models import Sum, F
    
    cache_key = "api_inv_items_v2"
    data = cache.get(cache_key)
    
    if not data:
        # Get items with their brand names and total quantities
        items = (
            InventoryItem.objects
            .annotate(brand_name=F('brand__name'))
            .values('name', 'brand_name')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('brand_name', 'name')
        )
        
        # Format the response
        formatted_items = [
            {
                'name': item['name'],
                'brand': item['brand_name'],
                'quantity': item['total_quantity'] or 0
            }
            for item in items
        ]
        
        data = {"items": formatted_items}
        cache.set(cache_key, data, 300)  # Cache for 5 minutes
        
    return JsonResponse(data)

@login_required
def api_inventory_brands(request: HttpRequest):
    from django.db.models import Sum, Min
    name = request.GET.get("name", "").strip()
    if not name:
        return JsonResponse({"brands": []})
    cache_key = f"api_inv_brands_{name}"
    data = cache.get(cache_key)
    if not data:
        # Aggregate by brand for this item
        rows = (
            InventoryItem.objects.filter(name=name)
            .values("brand")
            .annotate(quantity=Sum("quantity"), min_price=Min("price"))
            .order_by("brand")
        )
        non_empty = []
        unbranded_qty = 0
        unbranded_price = None
        for r in rows:
            b = (r["brand"] or "").strip()
            q = r["quantity"] or 0
            p = r["min_price"]
            if b:
                non_empty.append({"brand": b, "quantity": q, "price": str(p) if p is not None else ""})
            else:
                unbranded_qty += q
                if p is not None:
                    unbranded_price = p if unbranded_price is None else min(unbranded_price, p)
        brands = non_empty
        # Always include an aggregated Unbranded option when quantity exists
        if unbranded_qty > 0:
            brands.append({
                "brand": "Unbranded",
                "quantity": unbranded_qty,
                "price": str(unbranded_price) if unbranded_price is not None else ""
            })
        data = {"brands": brands}
        cache.set(cache_key, data, 120)
    return JsonResponse(data)

@login_required
def api_inventory_stock(request: HttpRequest):
    """API endpoint to check inventory stock for an item"""
    name = request.GET.get('name', '').strip()
    brand = request.GET.get('brand', '').strip()
    
    if not name or not brand:
        return JsonResponse({'error': 'Both name and brand parameters are required'}, status=400)
    
    try:
        item = InventoryItem.objects.get(name__iexact=name, brand__name__iexact=brand)
        return JsonResponse({
            'name': item.name,
            'brand': item.brand,
            'quantity': item.quantity,
            'unit': item.unit,
            'unit_price': item.unit_price
        })
    except InventoryItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)

@login_required
def vehicle_add(request: HttpRequest, customer_id: int):
    """Add a new vehicle for a customer"""
    customer = get_object_or_404(Customer, pk=customer_id)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.customer = customer
            vehicle.save()
            messages.success(request, 'Vehicle added successfully.')
            return redirect('tracker:customer_detail', pk=customer_id)
    else:
        form = VehicleForm()
    
    return render(request, 'tracker/vehicle_form.html', {
        'form': form,
        'customer': customer,
        'title': 'Add Vehicle'
    })


@login_required
def customer_delete(request: HttpRequest, pk: int):
    """Delete a customer and all associated data"""
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == 'POST':
        # Log the deletion before actually deleting
        try:
            add_audit_log(
                request.user,
                'customer_deleted',
                f'Deleted customer {customer.full_name} (ID: {customer.id})',
                customer_id=customer.id
            )
        except Exception:
            pass
        
        # Delete the customer (this will cascade to related objects)
        customer.delete()
        messages.success(request, f'Customer {customer.full_name} has been deleted.')
        return redirect('tracker:customers_list')
    
    # If not a POST request, redirect to customer detail
    return redirect('tracker:customer_detail', pk=customer.id)


@login_required
def vehicle_edit(request: HttpRequest, pk: int):
    """Edit an existing vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle updated successfully.')
            return redirect('tracker:customer_detail', pk=vehicle.customer_id)
    else:
        form = VehicleForm(instance=vehicle)
    
    return render(request, 'tracker/vehicle_form.html', {
        'form': form,
        'customer': vehicle.customer,
        'title': 'Edit Vehicle'
    })


@login_required
def vehicle_delete(request: HttpRequest, pk: int):
    """Delete a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    customer_id = vehicle.customer_id
    
    if request.method == 'POST':
        vehicle.delete()
        messages.success(request, 'Vehicle deleted successfully.')
        return redirect('tracker:customer_detail', pk=customer_id)
    
    return render(request, 'tracker/confirm_delete.html', {
        'object': vehicle,
        'cancel_url': reverse('tracker:customer_detail', kwargs={'pk': customer_id}),
        'item_type': 'vehicle'
    })


@login_required
def api_customer_vehicles(request: HttpRequest, customer_id: int):
    """API endpoint to get vehicles for a specific customer"""
    try:
        customer = Customer.objects.get(pk=customer_id)
        vehicles = [{
            'id': v.id,
            'make': v.make or '',
            'model': v.model or '',
            'year': getattr(v, 'year', None),
            'license_plate': v.plate_number or '',
            'vin': getattr(v, 'vin', '') or ''
        } for v in customer.vehicles.all()]

        return JsonResponse({
            'success': True,
            'vehicles': vehicles
        })
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)

@login_required
def api_notifications_summary(request: HttpRequest):
    """Return notification summary for header dropdown: today's visitors, low stock, overdue orders"""
    from datetime import timedelta
    stock_threshold = int(request.GET.get('stock_threshold', 5) or 5)
    overdue_hours = int(request.GET.get('overdue_hours', 24) or 24)

    today = timezone.localdate()
    now = timezone.now()
    cutoff = now - timedelta(hours=overdue_hours)

    # Today's visitors (arrival_time today)
    todays_qs = Customer.objects.filter(arrival_time__date=today).order_by('-arrival_time')
    todays_count = todays_qs.count()
    todays = [{
        'id': c.id,
        'name': c.full_name,
        'code': c.code,
        'time': c.arrival_time.isoformat() if c.arrival_time else None
    } for c in todays_qs[:8]]

    # Low stock items
    low_qs = InventoryItem.objects.filter(quantity__lte=stock_threshold).order_by('quantity', 'name')
    low_count = low_qs.count()
    low_stock = [{
        'id': i.id,
        'name': i.name,
        'brand': i.brand or 'Unbranded',
        'quantity': i.quantity
    } for i in low_qs[:8]]

    # Overdue orders (not completed, older than cutoff)
    overdue_qs = Order.objects.filter(status__in=['created','assigned','in_progress'], created_at__lt=cutoff).select_related('customer').order_by('created_at')
    overdue_count = overdue_qs.count()
    def age_minutes(dt):
        return int((now - dt).total_seconds() // 60) if dt else None
    overdue = [{
        'id': o.id,
        'order_number': o.order_number,
        'customer': o.customer.full_name,
        'status': o.status,
        'age_minutes': age_minutes(o.created_at)
    } for o in overdue_qs[:8]]

    total_new = todays_count + low_count + overdue_count
    return JsonResponse({
        'success': True,
        'counts': {
            'today_visitors': todays_count,
            'low_stock': low_count,
            'overdue_orders': overdue_count,
            'total': total_new,
        },
        'items': {
            'today_visitors': todays,
            'low_stock': low_stock,
            'overdue_orders': overdue,
        }
    })

# Permissions
is_manager = user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or u.groups.filter(name='manager').exists()))

@login_required
@is_manager
@csrf_exempt
@require_http_methods(["POST"])
@login_required
@is_manager
def create_brand(request):
    """API endpoint to create a new brand via AJAX"""
    from django.http import JsonResponse
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Brand name is required'}, status=400)
            
        # Check if brand already exists (case-insensitive)
        if Brand.objects.filter(name__iexact=name).exists():
            return JsonResponse({
                'success': False, 
                'error': f'A brand with the name "{name}" already exists.'
            }, status=400)
            
        # Create the brand
        brand = Brand.objects.create(
            name=name,
            description=data.get('description', '').strip(),
            website=data.get('website', '').strip()
        )
        
        return JsonResponse({
            'success': True,
            'brand': {
                'id': brand.id,
                'name': brand.name,
                'description': brand.description or '',
                'website': brand.website or ''
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@is_manager
def inventory_low_stock(request: HttpRequest):
    """View for displaying inventory items that are low in stock"""
    from .models import InventoryItem
    from django.db.models import Q, F, Sum, ExpressionWrapper, FloatField
    
    # Get threshold from query params or use default (items at or below reorder level)
    threshold = request.GET.get('threshold')
    try:
        threshold = int(threshold) if threshold else None
    except (ValueError, TypeError):
        threshold = None
    
    # Get low stock items
    if threshold is not None:
        # Use custom threshold from query params
        low_stock_items = InventoryItem.objects.filter(
            quantity__lte=threshold,
            is_active=True
        )
    else:
        # Use reorder level if no custom threshold provided
        low_stock_items = InventoryItem.objects.filter(
            quantity__lte=F('reorder_level'),
            is_active=True
        )
    
    # Annotate with total value
    low_stock_items = low_stock_items.annotate(
        total_value=ExpressionWrapper(
            F('price') * F('quantity'),
            output_field=FloatField()
        )
    ).order_by('quantity')
    
    # Calculate summary stats
    summary = {
        'total_items': low_stock_items.count(),
        'total_quantity': low_stock_items.aggregate(total=Sum('quantity'))['total'] or 0,
        'total_value': low_stock_items.aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0,
    }
    
    # Get items that are completely out of stock
    out_of_stock = low_stock_items.filter(quantity=0)
    
    context = {
        'items': low_stock_items,
        'out_of_stock': out_of_stock,
        'summary': summary,
        'threshold': threshold,
    }
    
    return render(request, 'tracker/inventory_low_stock.html', context)

@login_required
@is_manager
def inventory_stock_management(request: HttpRequest):
    """View for managing inventory stock levels and adjustments"""
    from .models import InventoryItem, InventoryAdjustment
    from .forms import InventoryAdjustmentForm
    from django.db.models import Sum, F, ExpressionWrapper, FloatField
    from django.db.models.functions import Coalesce
    from django.shortcuts import render, redirect
    from django.contrib import messages
    
    # Get all active inventory items with current stock levels
    items = InventoryItem.objects.filter(is_active=True).order_by('name')
    
    # Calculate total value for each item
    items = items.annotate(
        total_value=ExpressionWrapper(
            F('price') * F('quantity'),
            output_field=FloatField()
        )
    )
    
    # Handle stock adjustment form submission
    if request.method == 'POST':
        form = InventoryAdjustmentForm(request.POST)
        if form.is_valid():
            adjustment = form.save(commit=False)
            adjustment.user = request.user
            adjustment.save()
            
            # Update the inventory item quantity
            item = adjustment.item
            if adjustment.adjustment_type == 'add':
                item.quantity += adjustment.quantity
            else:
                item.quantity = max(0, item.quantity - adjustment.quantity)  # Prevent negative quantities
            item.save()
            
            messages.success(request, f'Stock level updated for {item.name}')
            return redirect('tracker:inventory_stock_management')
    else:
        form = InventoryAdjustmentForm()
    
    # Get recent adjustments
    recent_adjustments = InventoryAdjustment.objects.select_related('item', 'adjusted_by').order_by('-created_at')[:10]
    
    # Calculate inventory summary
    summary = {
        'total_items': items.count(),
        'total_quantity': items.aggregate(total=Sum('quantity'))['total'] or 0,
        'total_value': items.aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0,
        'low_stock_count': items.filter(quantity__lte=F('reorder_level')).count(),
    }
    
    return render(request, 'tracker/inventory_stock_management.html', {
        'items': items,
        'form': form,
        'recent_adjustments': recent_adjustments,
        'summary': summary,
    })


@login_required
@is_manager
def inventory_list(request: HttpRequest):
    # Get search parameters
    q = request.GET.get('q', '').strip()
    brand_filter = request.GET.get('brand', '').strip()
    
    # Start with base queryset - only fetch necessary fields for the list view
    qs = InventoryItem.objects.select_related('brand').only(
        'name', 'description', 'quantity', 'price', 'cost_price', 'sku', 'barcode',
        'reorder_level', 'is_active', 'created_at', 'brand__name'
    ).order_by('-created_at')
    
    # Apply search filter if provided
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(sku__icontains=q) |
            Q(barcode__icontains=q) |
            Q(brand__name__icontains=q)
        )
    
    # Apply brand filter if provided
    if brand_filter:
        try:
            brand_id = int(brand_filter)
            qs = qs.filter(brand_id=brand_id)
        except (ValueError, TypeError):
            # Invalid brand ID, ignore the filter
            pass
    
    # Get distinct active brands for filter dropdown
    # Cache this queryset since it's used in the template
    from django.core.cache import cache
    cache_key = 'active_brands_list'
    brands = cache.get(cache_key)
    
    if brands is None:
        brands = list(Brand.objects.filter(is_active=True).order_by('name').values('id', 'name'))
        # Cache for 1 hour
        cache.set(cache_key, brands, 3600)
    
    # Paginate results
    items_per_page = 20
    paginator = Paginator(qs, items_per_page)
    
    # Get current page from request
    page_number = request.GET.get('page')
    try:
        page_number = int(page_number) if page_number and page_number.isdigit() else 1
        items = paginator.page(page_number)
    except (ValueError, EmptyPage):
        # If page is not an integer or out of range, deliver first page
        items = paginator.page(1)
    
    # Calculate range of items being displayed
    start_index = (items.number - 1) * items_per_page + 1
    end_index = min(start_index + items_per_page - 1, paginator.count)
    
    context = {
        'items': items,
        'q': q,
        'brands': brands,
        'selected_brand': brand_filter,
        'total_items': paginator.count,
        'start_index': start_index,
        'end_index': end_index,
    }
    
    # Add HTTP headers for caching
    response = render(request, 'tracker/inventory_list.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'  # Prevent caching
    response['Pragma'] = 'no-cache'  # HTTP 1.0
    response['Expires'] = '0'  # Proxies
    
    return response

@login_required
@is_manager
def inventory_create(request: HttpRequest):
    from .forms import InventoryItemForm
    if request.method == 'POST':
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            from .utils import clear_inventory_cache
            clear_inventory_cache(item.name, item.brand)
            try:
                add_audit_log(request.user, 'inventory_create', f"Item '{item.name}' ({item.brand or 'Unbranded'}) qty={item.quantity}")
            except Exception:
                pass
            messages.success(request, 'Inventory item created')
            return redirect('tracker:inventory_list')
        else:
            messages.error(request, 'Please correct errors and try again')
    else:
        form = InventoryItemForm()
    return render(request, 'tracker/inventory_form.html', { 'form': form, 'mode': 'create' })

@login_required
@is_manager
def inventory_edit(request: HttpRequest, pk: int):
    from .forms import InventoryItemForm
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == 'POST':
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            item = form.save()
            from .utils import clear_inventory_cache
            clear_inventory_cache(item.name, item.brand)
            try:
                add_audit_log(request.user, 'inventory_update', f"Item '{item.name}' ({item.brand or 'Unbranded'}) now qty={item.quantity}")
            except Exception:
                pass
            messages.success(request, 'Inventory item updated')
            return redirect('tracker:inventory_list')
        else:
            messages.error(request, 'Please correct errors and try again')
    else:
        form = InventoryItemForm(instance=item)
    return render(request, 'tracker/inventory_form.html', { 'form': form, 'mode': 'edit', 'item': item })

@login_required
@is_manager
def inventory_delete(request: HttpRequest, pk: int):
    item = get_object_or_404(InventoryItem, pk=pk)
    if request.method == 'POST':
        from .utils import clear_inventory_cache
        name, brand = item.name, item.brand
        item.delete()
        clear_inventory_cache(name, brand)
        try:
            add_audit_log(request.user, 'inventory_delete', f"Deleted item '{name}' ({brand or 'Unbranded'})")
        except Exception:
            pass
        messages.success(request, 'Inventory item deleted')
        return redirect('tracker:inventory_list')
    return render(request, 'tracker/inventory_delete.html', { 'item': item })

# Admin-only: Organization Management
@login_required
@user_passes_test(lambda u: u.is_superuser)
def organization_management(request: HttpRequest):
    org_types = ['government', 'ngo', 'company']
    q = request.GET.get('q','').strip()
    status = request.GET.get('status','')
    sort_by = request.GET.get('sort','last_order_date')
    time_period = request.GET.get('period','6months')

    # Period
    today = timezone.now().date()
    if time_period == '1month':
        start_date = today - timezone.timedelta(days=30)
    elif time_period == '3months':
        start_date = today - timezone.timedelta(days=90)
    elif time_period == '1year':
        start_date = today - timezone.timedelta(days=365)
    else:
        start_date = today - timezone.timedelta(days=180)

    base = Customer.objects.filter(customer_type__in=org_types)
    if q:
        base = base.filter(Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q) | Q(organization_name__icontains=q) | Q(code__icontains=q))

    customers_qs = base.annotate(
        recent_orders_count=Count('orders', filter=Q(orders__created_at__date__gte=start_date)),
        last_order_date=Max('orders__created_at'),
        service_orders=Count('orders', filter=Q(orders__type='service', orders__created_at__date__gte=start_date)),
        sales_orders=Count('orders', filter=Q(orders__type='sales', orders__created_at__date__gte=start_date)),
        consultation_orders=Count('orders', filter=Q(orders__type='consultation', orders__created_at__date__gte=start_date)),
        completed_orders=Count('orders', filter=Q(orders__status='completed', orders__created_at__date__gte=start_date)),
        cancelled_orders=Count('orders', filter=Q(orders__status='cancelled', orders__created_at__date__gte=start_date)),
        vehicles_count=Count('vehicles', distinct=True)
    )

    if status == 'returning':
        customers_qs = customers_qs.filter(total_visits__gt=1)

    if sort_by in ['recent_orders_count','total_spent','last_order_date','vehicles_count','completed_orders']:
        customers_qs = customers_qs.order_by(f'-{sort_by}')
    else:
        customers_qs = customers_qs.order_by('-last_order_date')

    paginator = Paginator(customers_qs, 20)
    page = request.GET.get('page')
    customers = paginator.get_page(page)

    # Header counts
    type_counts = base.values('customer_type').annotate(c=Count('id'))
    counts = {row['customer_type']: row['c'] for row in type_counts}
    total_org = sum(counts.values()) if counts else 0

    # Charts
    orders_scope = Order.objects.filter(customer__in=base, created_at__date__gte=start_date)
    if status == 'returning':
        orders_scope = orders_scope.filter(customer__total_visits__gt=1)
    type_dist = {r['type']: r['c'] for r in orders_scope.values('type').annotate(c=Count('id'))}
    from django.db.models.functions import TruncMonth
    month_rows = orders_scope.annotate(m=TruncMonth('created_at')).values('m').annotate(c=Count('id')).order_by('m')
    trend_labels = [(r['m'].strftime('%Y-%m') if r['m'] else '') for r in month_rows]
    trend_values = [r['c'] for r in month_rows]
    charts = {
        'type': {
            'labels': ['Service','Sales','Consultation'],
            'values': [type_dist.get('service',0), type_dist.get('sales',0), type_dist.get('consultation',0)]
        },
        'trend': {'labels': trend_labels, 'values': trend_values}
    }

    return render(request, 'tracker/organization.html', {
        'customers': customers,
        'q': q,
        'counts': counts,
        'total_org': total_org,
        'status': status,
        'sort_by': sort_by,
        'time_period': time_period,
        'start_date': start_date,
        'end_date': today,
        'charts_json': json.dumps(charts),
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def organization_export(request: HttpRequest):
    org_types = ['government','ngo','company']
    q = request.GET.get('q','').strip()
    status = request.GET.get('status','')
    time_period = request.GET.get('period','6months')
    today = timezone.now().date()
    if time_period == '1month':
        start_date = today - timezone.timedelta(days=30)
    elif time_period == '3months':
        start_date = today - timezone.timedelta(days=90)
    elif time_period == '1year':
        start_date = today - timezone.timedelta(days=365)
    else:
        start_date = today - timezone.timedelta(days=180)

    base = Customer.objects.filter(customer_type__in=org_types)
    if q:
        base = base.filter(Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q) | Q(organization_name__icontains=q) | Q(code__icontains=q))
    qs = base.annotate(
        recent_orders_count=Count('orders', filter=Q(orders__created_at__date__gte=start_date)),
        last_order_date=Max('orders__created_at'),
        service_orders=Count('orders', filter=Q(orders__type='service', orders__created_at__date__gte=start_date)),
        sales_orders=Count('orders', filter=Q(orders__type='sales', orders__created_at__date__gte=start_date)),
        consultation_orders=Count('orders', filter=Q(orders__type='consultation', orders__created_at__date__gte=start_date)),
        completed_orders=Count('orders', filter=Q(orders__status='completed', orders__created_at__date__gte=start_date)),
        vehicles_count=Count('vehicles', distinct=True),
    )
    if status == 'returning':
        qs = qs.filter(total_visits__gt=1)

    import csv
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="organization_customers.csv"'
    w = csv.writer(resp)
    w.writerow(['Code','Organization','Contact','Phone','Type','Visits','Orders (period)','Service','Sales','Consult','Completed','Vehicles','Last Order'])
    for c in qs.iterator():
        w.writerow([
            c.code,
            c.organization_name or '',
            c.full_name,
            c.phone,
            c.customer_type,
            c.total_visits,
            c.recent_orders_count,
            c.service_orders,
            c.sales_orders,
            c.consultation_orders,
            c.completed_orders,
            c.vehicles_count,
            c.last_order_date.isoformat() if c.last_order_date else ''
        ])
    return resp

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def users_list(request: HttpRequest):
    q = request.GET.get('q','').strip()
    qs = User.objects.all().order_by('-date_joined')
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    return render(request, 'tracker/users_list.html', { 'users': qs[:100], 'q': q })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_create(request: HttpRequest):
    from .forms import AdminUserCreateForm
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            add_audit_log(request.user, 'user_create', f'Created user {new_user.username}')
            messages.success(request, 'User created')
            return redirect('tracker:users_list')
        else:
            messages.error(request, 'Please correct errors and try again')
    else:
        form = AdminUserCreateForm()
    return render(request, 'tracker/user_create.html', { 'form': form })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_edit(request: HttpRequest, pk: int):
    from .forms import AdminUserForm
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = AdminUserForm(request.POST, instance=u)
        if form.is_valid():
            updated_user = form.save()
            add_audit_log(request.user, 'user_update', f'Updated user {updated_user.username}')
            messages.success(request, 'User updated')
            return redirect('tracker:users_list')
        else:
            messages.error(request, 'Please correct errors and try again')
    else:
        form = AdminUserForm(instance=u)
    return render(request, 'tracker/user_edit.html', { 'form': form, 'user_obj': u })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_toggle_active(request: HttpRequest, pk: int):
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        u.is_active = not u.is_active
        u.save(update_fields=['is_active'])
        add_audit_log(request.user, 'user_toggle_active', f'Toggled active for {u.username} -> {u.is_active}')
        messages.success(request, f'User {"activated" if u.is_active else "deactivated"}.')
    return redirect('tracker:users_list')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_reset_password(request: HttpRequest, pk: int):
    import random, string
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        temp = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        u.set_password(temp)
        u.save()
        add_audit_log(request.user, 'user_reset_password', f'Reset password for {u.username}')
        messages.success(request, f'Temporary password for {u.username}: {temp}')
    return redirect('tracker:users_list')


@login_required
def customer_edit(request: HttpRequest, pk: int):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerEditForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            try:
                add_audit_log(request.user, 'customer_update', f"Updated customer {customer.full_name} ({customer.code})")
            except Exception:
                pass
            messages.success(request, 'Customer updated successfully')
            return redirect('tracker:customer_detail', pk=customer.id)
        else:
            messages.error(request, 'Please correct errors and try again')
    else:
        form = CustomerEditForm(instance=customer)
    return render(request, 'tracker/customer_edit.html', { 'form': form, 'customer': customer })


@login_required
def customers_quick_create(request: HttpRequest):
    """Quick customer creation for order form"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            full_name = request.POST.get('full_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            customer_type = request.POST.get('customer_type', 'personal')

            if not full_name or not phone:
                return JsonResponse({'success': False, 'message': 'Name and phone are required'})

            # Normalize phone number (remove all non-digit characters)
            import re
            normalized_phone = re.sub(r'\D', '', phone)
            
            # Check for existing customers with similar name and phone
            existing_customers = Customer.objects.filter(
                full_name__iexact=full_name
            )
            
            # Check each potential match for phone number similarity
            for customer in existing_customers:
                # Normalize stored phone number for comparison
                stored_phone = re.sub(r'\D', '', str(customer.phone))
                # Check for exact or partial match (at least 6 digits matching)
                if len(normalized_phone) >= 6 and len(stored_phone) >= 6:
                    if normalized_phone in stored_phone or stored_phone in normalized_phone:
                        return JsonResponse({
                            'success': False, 
                            'message': f'A similar customer already exists: {customer.full_name} ({customer.phone})',
                            'customer_id': customer.id,
                            'customer_name': customer.full_name,
                            'customer_phone': str(customer.phone)
                        })

            # Create customer
            customer = Customer.objects.create(
                full_name=full_name,
                phone=phone,
                email=email if email else None,
                customer_type=customer_type
            )

            try:
                add_audit_log(request.user, 'customer_create', f"Created customer {customer.full_name} ({customer.code})")
            except Exception:
                pass

            return JsonResponse({
                'success': True,
                'message': 'Customer created successfully',
                'customer': {
                    'id': customer.id,
                    'name': customer.full_name,
                    'phone': customer.phone,
                    'email': customer.email or '',
                    'code': customer.code,
                    'type': customer.customer_type
                }
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error creating customer: {str(e)}'})

    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def inquiries(request: HttpRequest):
    """View and manage customer inquiries"""
    # Get filter parameters
    inquiry_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    follow_up = request.GET.get('follow_up', '')

    # Base queryset for consultation orders (inquiries)
    queryset = Order.objects.filter(type='consultation').select_related('customer').order_by('-created_at')

    # Apply filters
    if inquiry_type:
        queryset = queryset.filter(inquiry_type=inquiry_type)

    if status:
        queryset = queryset.filter(status=status)

    if follow_up == 'required':
        queryset = queryset.filter(follow_up_date__isnull=False)
    elif follow_up == 'overdue':
        today = timezone.localdate()
        queryset = queryset.filter(
            follow_up_date__lte=today,
            status__in=['created', 'in_progress']
        )

    # Pagination
    paginator = Paginator(queryset, 12)  # Show 12 inquiries per page
    page = request.GET.get('page')
    inquiries = paginator.get_page(page)

    # Statistics
    stats = {
        'new': Order.objects.filter(type='consultation', status='created').count(),
        'in_progress': Order.objects.filter(type='consultation', status='in_progress').count(),
        'resolved': Order.objects.filter(type='consultation', status='completed').count(),
    }

    context = {
        'inquiries': inquiries,
        'stats': stats,
        'today': timezone.localdate(),
    }

    return render(request, 'tracker/inquiries.html', context)


@login_required
def inquiry_detail(request: HttpRequest, pk: int):
    """Get inquiry details for modal view"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            inquiry = get_object_or_404(Order, pk=pk, type='consultation')

            data = {
                'id': inquiry.id,
                'customer': {
                    'name': inquiry.customer.full_name,
                    'phone': inquiry.customer.phone,
                    'email': inquiry.customer.email or '',
                },
                'inquiry_type': inquiry.inquiry_type or 'General',
                'contact_preference': inquiry.contact_preference or 'Phone',
                'questions': inquiry.questions or '',
                'status': inquiry.status,
                'status_display': inquiry.get_status_display(),
                'created_at': inquiry.created_at.isoformat(),
                'follow_up_date': inquiry.follow_up_date.isoformat() if inquiry.follow_up_date else None,
                'responses': [],  # In a real app, you'd have a related model for responses
            }

            return JsonResponse(data)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def inquiry_respond(request: HttpRequest, pk: int):
    """Respond to a customer inquiry"""
    from .utils import send_sms
    inquiry = get_object_or_404(Order, pk=pk, type='consultation')

    if request.method == 'POST':
        response_text = request.POST.get('response', '').strip()
        follow_up_required = request.POST.get('follow_up_required') == 'on'
        follow_up_date = request.POST.get('follow_up_date')

        if not response_text:
            messages.error(request, 'Response message is required')
            return redirect('tracker:inquiries')

        # Append response into inquiry questions thread
        stamp = timezone.now().strftime('%Y-%m-%d %H:%M')
        trail = f"[{stamp}] Response: {response_text}"
        if inquiry.questions:
            inquiry.questions = (inquiry.questions or '') + "\n\n" + trail
        else:
            inquiry.questions = trail

        # Update follow-up date if required
        if follow_up_required and follow_up_date:
            try:
                inquiry.follow_up_date = follow_up_date
            except ValueError:
                pass

        # Mark as in progress if not already completed
        if inquiry.status == 'created':
            inquiry.status = 'in_progress'

        inquiry.save()
        try:
            add_audit_log(request.user, 'inquiry_respond', f"Responded to inquiry #{inquiry.id} for {inquiry.customer.full_name}")
        except Exception:
            pass

        # Send SMS to the customer's phone
        phone = inquiry.customer.phone
        sms_message = f"Hello {inquiry.customer.full_name}, regarding your inquiry ({inquiry.inquiry_type or 'General'}): {response_text} — Superdoll Support"
        ok, info = send_sms(phone, sms_message)
        if ok:
            messages.success(request, 'Response sent via SMS')
        else:
            messages.warning(request, f'Response saved, but SMS not sent: {info}')
        return redirect('tracker:inquiries')

    return redirect('tracker:inquiries')


@login_required
def update_inquiry_status(request: HttpRequest, pk: int):
    """Update inquiry status"""
    inquiry = get_object_or_404(Order, pk=pk, type='consultation')

    if request.method == 'POST':
        new_status = request.POST.get('status')

        if new_status in ['created', 'in_progress', 'completed']:
            old_status = inquiry.status
            inquiry.status = new_status

            if new_status == 'completed':
                inquiry.completed_at = timezone.now()

            inquiry.save()
            try:
                add_audit_log(request.user, 'inquiry_status_update', f"Inquiry #{inquiry.id}: {old_status} -> {new_status}")
            except Exception:
                pass

            status_display = {
                'created': 'New',
                'in_progress': 'In Progress',
                'completed': 'Resolved'
            }

            messages.success(request, f'Inquiry status updated to {status_display.get(new_status, new_status)}')
        else:
            messages.error(request, 'Invalid status')

    return redirect('tracker:inquiries')


@login_required
def reports_advanced(request: HttpRequest):
    """Advanced reports with period and type filters"""
    from datetime import timedelta, datetime, time as dt_time

    period = request.GET.get('period', 'monthly')
    report_type = request.GET.get('type', 'overview')

    # Calculate date range based on period
    today = timezone.localdate()
    if period == 'daily':
        start_date = today
        end_date = today
        date_format = '%H:%M'
        labels = [f"{i:02d}:00" for i in range(24)]
    elif period == 'weekly':
        start_date = today - timedelta(days=6)
        end_date = today
        date_format = '%a'
        labels = [(start_date + timedelta(days=i)).strftime('%a') for i in range(7)]
    elif period == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
        date_format = '%b'
        labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    else:  # monthly
        start_date = today - timedelta(days=29)
        end_date = today
        date_format = '%d'
        labels = [(start_date + timedelta(days=i)).strftime('%d') for i in range(30)]

    # Compute timezone-aware datetime range [start_dt, end_dt)
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, dt_time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), dt_time.min), tz)

    # Reuse filtered querysets for consistency
    qs = Order.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt)
    cqs = Customer.objects.filter(registration_date__gte=start_dt, registration_date__lt=end_dt)

    # Base statistics
    total_orders = qs.count()
    # Completed counted by completion time within the selected period
    completed_orders = Order.objects.filter(
        completed_at__gte=start_dt,
        completed_at__lt=end_dt,
        status='completed',
    ).count()
    pending_orders = qs.filter(status__in=['created', 'assigned', 'in_progress']).count()
    total_customers = cqs.count()

    completion_rate = int((completed_orders * 100) / total_orders) if total_orders > 0 else 0

    # Average duration
    avg_duration_qs = qs.filter(
        actual_duration__isnull=False
    ).aggregate(avg_duration=Avg('actual_duration'))
    avg_duration = int(avg_duration_qs['avg_duration'] or 0)

    stats = {
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'pending_orders': pending_orders,
        'total_customers': total_customers,
        'completion_rate': completion_rate,
        'avg_duration': avg_duration,
        'new_customers': total_customers,
        'avg_service_time': avg_duration,
        # Order type breakdown
        'service_orders': qs.filter(type='service').count(),
        'sales_orders': qs.filter(type='sales').count(),
        'consultation_orders': qs.filter(type='consultation').count(),
    }

    # Calculate percentages
    if total_orders > 0:
        stats['service_percentage'] = int((stats['service_orders'] * 100) / total_orders)
        stats['sales_percentage'] = int((stats['sales_orders'] * 100) / total_orders)
        stats['consultation_percentage'] = int((stats['consultation_orders'] * 100) / total_orders)
    else:
        stats['service_percentage'] = stats['sales_percentage'] = stats['consultation_percentage'] = 0

    # Real trend data per selected period
    qs = Order.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt)
    if period == 'daily':
        from django.db.models.functions import ExtractHour
        trend_map = {int(r['h'] or 0): r['c'] for r in qs.annotate(h=ExtractHour('created_at')).values('h').annotate(c=Count('id'))}
        trend_values = [trend_map.get(h, 0) for h in range(24)]
    elif period == 'weekly':
        by_date = {r['day']: r['c'] for r in qs.annotate(day=TruncDate('created_at')).values('day').annotate(c=Count('id'))}
        trend_values = [(by_date.get(start_date + timedelta(days=i), 0)) for i in range(7)]
    elif period == 'yearly':
        from django.db.models.functions import ExtractMonth
        by_month = {int(r['m']): r['c'] for r in qs.annotate(m=ExtractMonth('created_at')).values('m').annotate(c=Count('id'))}
        trend_values = [by_month.get(i, 0) for i in range(1, 13)]
    else:  # monthly
        by_date = {r['day']: r['c'] for r in qs.annotate(day=TruncDate('created_at')).values('day').annotate(c=Count('id'))}
        trend_values = [(by_date.get(start_date + timedelta(days=i), 0)) for i in range(30)]

    chart_data = {
        'trend': { 'labels': labels, 'values': trend_values },
        'status': {
            'labels': ['Created', 'Assigned', 'In Progress', 'Completed', 'Cancelled'],
            'values': [
                qs.filter(status='created').count(),
                qs.filter(status='assigned').count(),
                qs.filter(status='in_progress').count(),
                Order.objects.filter(completed_at__gte=start_dt, completed_at__lt=end_dt, status='completed').count(),
                qs.filter(status='cancelled').count(),
            ]
        },
        'orders': {
            'labels': ['Service', 'Sales', 'Consultation'],
            'values': [stats['service_orders'], stats['sales_orders'], stats['consultation_orders']]
        },
        'types': {
            'labels': ['Personal', 'Company', 'Government', 'NGO', 'Bodaboda'],
            'values': [
                cqs.filter(customer_type='personal').count(),
                cqs.filter(customer_type='company').count(),
                cqs.filter(customer_type='government').count(),
                cqs.filter(customer_type='ngo').count(),
                cqs.filter(customer_type='bodaboda').count(),
            ]
        }
    }

    # Get data items based on report type
    if report_type == 'customers':
        data_items = cqs.order_by('-registration_date')[:20]
    elif report_type == 'inquiries':
        data_items = qs.filter(type='consultation').select_related('customer').order_by('-created_at')[:20]
    else:
        data_items = qs.select_related('customer').order_by('-created_at')[:20]

    context = {
        'period': period,
        'report_type': report_type,
        'stats': stats,
        'chart_data': json.dumps(chart_data),
        'data_items': data_items,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    }

    return render(request, 'tracker/reports_advanced.html', context)

# ---------------------------
# System settings and admin
# ---------------------------
@login_required
@user_passes_test(lambda u: u.is_superuser)
def system_settings(request: HttpRequest):
    def defaults():
        return {
            'company_name': '',
            'default_priority': 'medium',
            'enable_unbranded_alias': True,
            'allow_order_without_vehicle': True,
            'sms_provider': 'none',
        }
    data = cache.get('system_settings', None) or defaults()
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST)
        if form.is_valid():
            new_data = {**defaults(), **form.cleaned_data}
            changes = []
            for k, old_val in (data or {}).items():
                new_val = new_data.get(k)
                if new_val != old_val:
                    changes.append(f"{k}: '{old_val}' -> '{new_val}'")
            cache.set('system_settings', new_data, None)
            add_audit_log(request.user, 'system_settings_update', '; '.join(changes) if changes else 'No changes')
            messages.success(request, 'Settings updated')
            return redirect('tracker:system_settings')
        else:
            messages.error(request, 'Please correct errors and try again')
    else:
        form = SystemSettingsForm(initial=data)
    return render(request, 'tracker/system_settings.html', {'form': form, 'settings': data})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def audit_logs(request: HttpRequest):
    if request.method == 'POST' and request.POST.get('action') == 'clear':
        clear_audit_logs()
        add_audit_log(request.user, 'audit_logs_cleared', 'Cleared all audit logs')
        messages.success(request, 'Audit logs cleared')
        return redirect('tracker:audit_logs')
    
    q = request.GET.get('q', '').strip()
    action_filter = request.GET.get('action', '').strip()
    user_filter = request.GET.get('user', '').strip()
    
    logs = get_audit_logs()
    
    if q or action_filter or user_filter:
        filtered_logs = []
        for log in logs:
            # Convert all searchable fields to lowercase for case-insensitive search
            log_user = str(log.get('user', '')).lower()
            log_action = str(log.get('action', '')).lower()
            log_description = str(log.get('description', '')).lower()
            log_meta = str(log.get('meta', {})).lower()
            
            # Apply filters
            matches = True
            
            # General search (q parameter)
            if q:
                q = q.lower()
                if not (q in log_user or q in log_action or q in log_description or q in log_meta):
                    matches = False
            
            # Action filter
            if matches and action_filter:
                if action_filter.lower() not in log_action:
                    matches = False
            
            # User filter
            if matches and user_filter:
                if user_filter.lower() not in log_user:
                    matches = False
            
            if matches:
                filtered_logs.append(log)
        logs = filtered_logs
    
    # Get unique actions and users for filter dropdowns
    all_actions = sorted(set(log.get('action', '') for log in get_audit_logs() if log.get('action')))
    all_users = sorted(set(log.get('user', '') for log in get_audit_logs() if log.get('user')))
    
    context = {
        'logs': logs,
        'q': q,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'all_actions': all_actions,
        'all_users': all_users,
    }
    return render(request, 'tracker/audit_logs.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def backup_restore(request: HttpRequest):
    if request.GET.get('download'):
        import json
        payload = {
            'system_settings': cache.get('system_settings', {}),
        }
        add_audit_log(request.user, 'backup_download', 'Downloaded system settings backup')
        resp = HttpResponse(json.dumps(payload, indent=2), content_type='application/json')
        resp['Content-Disposition'] = 'attachment; filename="backup.json"'
        return resp
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reset_settings':
            cache.delete('system_settings')
            add_audit_log(request.user, 'settings_reset', 'Reset system settings to defaults')
            messages.success(request, 'System settings have been reset to defaults')
            return redirect('tracker:backup_restore')
        if action == 'restore_settings' and request.FILES.get('file'):
            f = request.FILES['file']
            try:
                data = json.load(f)
                settings_data = data.get('system_settings') or {}
                if isinstance(settings_data, dict):
                    cache.set('system_settings', settings_data, None)
                    add_audit_log(request.user, 'settings_restored', 'Restored system settings from uploaded backup')
                    messages.success(request, 'Settings restored from backup')
                else:
                    messages.error(request, 'Invalid backup file format')
            except Exception as e:
                messages.error(request, f'Failed to restore: {e}')
            return redirect('tracker:backup_restore')
    return render(request, 'tracker/backup_restore.html')


# ---------------------------
# Reports System
# ---------------------------
# All report views are now in the reports.py module
# These are just aliases for backward compatibility

    

# ---------------------------
# Analytics Sub-Pages
# ---------------------------

@login_required
def analytics_performance(request: HttpRequest):
    """Temporary stub view to satisfy URL mapping; can be expanded later."""
    # Reuse the main analytics view output for now
    return analytics(request)

@login_required
def analytics_customer(request: HttpRequest):
    """Customer analytics page with period filters and charts"""
    # Filters: from/to or period
    f_from = request.GET.get("from")
    f_to = request.GET.get("to")
    period = request.GET.get("period", "")
    today = timezone.localdate()
    if (not f_from or not f_to) and period:
        if period == "daily":
            f_from = f_from or today.isoformat()
            f_to = f_to or today.isoformat()
        elif period == "weekly":
            start = today - timezone.timedelta(days=6)
            f_from = f_from or start.isoformat()
            f_to = f_to or today.isoformat()
        elif period == "yearly":
            start = today.replace(month=1, day=1)
            f_from = f_from or start.isoformat()
            f_to = f_to or today.isoformat()
        else:  # monthly default (last 30 days)
            start = today - timezone.timedelta(days=29)
            f_from = f_from or start.isoformat()
            f_to = f_to or today.isoformat()

    qs = Customer.objects.all()
    if f_from:
        try:
            qs = qs.filter(registration_date__date__gte=f_from)
        except Exception:
            pass
    if f_to:
        try:
            qs = qs.filter(registration_date__date__lte=f_to)
        except Exception:
            pass

    # KPIs
    totals = {
        "new_customers": qs.count(),
        "total_customers": Customer.objects.count(),
        "with_email": qs.exclude(email__isnull=True).exclude(email="").count(),
        "with_phone": qs.exclude(phone__isnull=True).exclude(phone="").count(),
    }

    # Trend of new customers
    trend_map = {
        row["day"]: row["c"]
        for row in qs.annotate(day=TruncDate("registration_date")).values("day").annotate(c=Count("id"))
    }
    labels = []
    values = []
    if f_from and f_to:
        try:
            from datetime import date, timedelta
            start = date.fromisoformat(f_from)
            end = date.fromisoformat(f_to)
            if start > end:
                start, end = end, start
            days = (end - start).days
            for i in range(days + 1):
                d = start + timedelta(days=i)
                labels.append(d.isoformat())
                values.append(trend_map.get(d, 0))
        except Exception:
            pass
    if not labels:
        # Build a minimal range to avoid empty charts
        if trend_map:
            for d, c in sorted(trend_map.items()):
                labels.append(d.isoformat() if hasattr(d, "isoformat") else str(d))
                values.append(c)
        else:
            # Default to last 7 days placeholders
            from datetime import date, timedelta
            end = today
            start = end - timedelta(days=6)
            for i in range(7):
                d = start + timedelta(days=i)
                labels.append(d.isoformat())
                values.append(0)

    # By type distribution
    type_counts = {row["customer_type"]: row["c"] for row in qs.values("customer_type").annotate(c=Count("id"))}

    # Top customers by visits and spend (overall, not only period-limited)
    from django.db.models import Max
    top_customers = (
        Customer.objects.annotate(order_count=Count("orders"), latest_order_date=Max("orders__created_at"))
        .filter(order_count__gt=0)
        .order_by("-order_count")[:10]
    )

    charts = {
        "trend": {"labels": labels, "values": values},
        "types": {
            "labels": [
                "Government",
                "NGO",
                "Private Company",
                "Personal",
                "Bodaboda",
            ],
            "values": [
                type_counts.get("government", 0),
                type_counts.get("ngo", 0),
                type_counts.get("company", 0),
                type_counts.get("personal", 0),
                type_counts.get("bodaboda", 0),
            ],
        },
    }

    return render(
        request,
        "tracker/analytics_customer.html",
        {
            "page_title": "Customer Analytics",
            "period": period or ("monthly" if not f_from and not f_to else "custom"),
            "export_from": f_from or (labels[0] if labels else ""),
            "export_to": f_to or (labels[-1] if labels else ""),
            "charts_json": json.dumps(charts),
            "totals": totals,
            "top_customers": top_customers,
            "today": timezone.localdate(),
        }
    )

@login_required
def analytics_service(request: HttpRequest):
    """Service analytics using real Order data (sales/service/consultation)."""
    from datetime import datetime
    # Filters
    f_from = request.GET.get("from")
    f_to = request.GET.get("to")
    period = request.GET.get("period", "monthly")
    today = timezone.localdate()

    # Resolve period shortcuts
    if period == "daily" or (not f_from and not f_to and not period):
        f_from = f_from or today.isoformat()
        f_to = f_to or today.isoformat()
        period = "daily"
    elif period == "weekly":
        start = today - timezone.timedelta(days=6)
        f_from = f_from or start.isoformat()
        f_to = f_to or today.isoformat()
    elif period == "yearly":
        start = today.replace(month=1, day=1)
        f_from = f_from or start.isoformat()
        f_to = f_to or today.isoformat()
    else:  # monthly (last 30 days)
        start = today - timezone.timedelta(days=29)
        f_from = f_from or start.isoformat()
        f_to = f_to or today.isoformat()
        period = "monthly"

    # Parse dates
    def parse_d(s):
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None
    start_date = parse_d(f_from) or today
    end_date = parse_d(f_to) or today

    # Query base within created_at date range
    qs = Order.objects.all().select_related("customer")
    qs = qs.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

    # Counts by type and status
    by_type = {r["type"] or "": r["c"] for r in qs.values("type").annotate(c=Count("id"))}
    by_status = {r["status"] or "": r["c"] for r in qs.values("status").annotate(c=Count("id"))}

    # Status by type matrix for stacked chart
    status_order = ["created", "assigned", "in_progress", "completed", "cancelled"]
    type_order = ["sales", "service", "consultation"]
    status_by_app = { (r["type"] or "", r["status"] or ""): r["c"] for r in qs.values("type", "status").annotate(c=Count("id")) }
    status_series = [
        {
            "name": t.title(),
            "data": [status_by_app.get((t, s), 0) for s in status_order],
        }
        for t in type_order
    ]

    # Trend data per day by type
    trend_days = (end_date - start_date).days + 1
    trend_labels = [(start_date + timezone.timedelta(days=i)).strftime("%b %d") for i in range(trend_days)]
    trend_map = {
        (row["day"], row["type"]): row["c"]
        for row in qs.annotate(day=TruncDate("created_at")).values("day", "type").annotate(c=Count("id"))
    }
    trend_series = []
    for t in type_order:
        values = [trend_map.get((start_date + timezone.timedelta(days=i), t), 0) for i in range(trend_days)]
        trend_series.append({"name": t.title(), "values": values})

    # Sales breakdowns
    sales_qs = qs.filter(type="sales")
    top_brands_qs = sales_qs.values("brand").annotate(c=Count("id")).order_by("-c")[:8]
    top_brands = {
        "labels": [r["brand"] or "Unknown" for r in top_brands_qs],
        "values": [r["c"] for r in top_brands_qs],
    }
    tire_types_qs = sales_qs.values("tire_type").annotate(c=Count("id")).order_by("-c")
    tire_types = {
        "labels": [r["tire_type"] or "Unknown" for r in tire_types_qs],
        "values": [r["c"] for r in tire_types_qs],
    }

    # Inquiry breakdowns
    inquiry_qs = qs.filter(type="consultation")
    inquiry_types_qs = inquiry_qs.values("inquiry_type").annotate(c=Count("id")).order_by("-c")
    inquiry_types = {
        "labels": [r["inquiry_type"] or "Other" for r in inquiry_types_qs],
        "values": [r["c"] for r in inquiry_types_qs],
    }

    # Types pie
    types_chart = {
        "labels": ["Sales", "Service", "Consultation"],
        "values": [by_type.get("sales", 0), by_type.get("service", 0), by_type.get("consultation", 0)],
    }

    # KPIs + period-over-period deltas
    total_orders = sum(types_chart["values"]) if types_chart else 0
    total_sales = by_type.get("sales", 0)
    total_service = by_type.get("service", 0)
    total_inquiries = by_type.get("consultation", 0)

    # Previous period (same length right before start_date)
    prev_end = start_date - timezone.timedelta(days=1)
    prev_start = prev_end - timezone.timedelta(days=trend_days - 1)
    prev_qs = Order.objects.filter(created_at__date__gte=prev_start, created_at__date__lte=prev_end)
    def pct_change(curr, prev):
        return round(((curr - prev) * 100.0) / (prev if prev else 1), 1)
    prev_by_type = {r["type"] or "": r["c"] for r in prev_qs.values("type").annotate(c=Count("id"))}
    kpis = {
        "total_orders": total_orders,
        "total_tire_sales": total_sales,
        "total_car_service": total_service,
        "total_inquiries": total_inquiries,
        "order_change": pct_change(total_orders, sum(prev_by_type.values()) if prev_by_type else 0),
        "tire_sales_change": pct_change(total_sales, prev_by_type.get("sales", 0)),
        "car_service_change": pct_change(total_service, prev_by_type.get("service", 0)),
        "inquiry_change": pct_change(total_inquiries, prev_by_type.get("consultation", 0)),
    }

    charts = {
        "trend_multi": {"labels": trend_labels, "series": trend_series},
        "types": types_chart,
        "status_by_app": {"apps": [s.replace("_", " ").title() for s in status_order], "series": status_series},
        "top_brands": top_brands,
        "tire_types": tire_types,
        "inquiry_types": inquiry_types,
    }

    context = {
        "page_title": "Service Analytics",
        "period": period,
        "f_from": start_date.isoformat(),
        "f_to": end_date.isoformat(),
        "today": today.isoformat(),
        "by_type": by_type,
        "by_type_values_sum": total_orders,
        "kpis": kpis,
        "charts_json": json.dumps(charts),
    }
    return render(request, "tracker/analytics_service.html", context)
