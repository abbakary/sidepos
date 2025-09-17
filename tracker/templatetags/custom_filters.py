from django import template
from decimal import Decimal, DivisionByZero
from django.utils import timezone
from datetime import timedelta
import math
from typing import Union, Optional
from django import template

register = template.Library()

@register.filter(name='div')
def div(value, arg):
    """
    Divides the value by the argument.
    Usage: {{ value|div:arg }}
    Returns 0 if division by zero occurs.
    """
    try:
        if value is None or arg is None:
            return 0
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter(name='mul')
def mul(value, arg):
    """
    Multiplies the value by the argument.
    Usage: {{ value|mul:arg }}
    Returns 0 if multiplication fails.
    """
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='timesince_days')
def timesince_days(value):
    """
    Returns the number of days between the given date and now.
    Usage: {{ date|timesince_days }}
    """
    if not value:
        return 0
    
    try:
        now = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value)
        delta = now - value
        return delta.days
    except (TypeError, ValueError):
        return 0

@register.filter(name='replace')
def replace(value, arg):
    """
    Replaces all occurrences of a substring with another substring.
    Usage: {{ value|replace:"old:new" }}
    """
    if not value:
        return value

    try:
        if ':' in arg:
            old, new = arg.split(':', 1)
            return str(value).replace(old, new)
        return str(value).replace(arg, '')
    except (ValueError, AttributeError):
        return value

@register.filter(name='dict_get')
def dict_get(d, key):
    """
    Safely get a value from a dictionary using a key.
    Usage: {{ my_dict|dict_get:key_name }}
    Returns None if the key doesn't exist or if there's an error.
    """
    try:
        if d and hasattr(d, 'get'):
            return d.get(key)
        return None
    except Exception:
        return None

@register.filter(name='to_css_class')
def to_css_class(value):
    """
    Convert a value to a CSS-friendly class suffix.
    - Lowercases, trims, replaces underscores with hyphens.
    - Maps known order statuses to friendly names used in CSS.
      created -> pending
      assigned -> in-progress
      in_progress -> in-progress
      completed -> completed
      cancelled -> cancelled
    Priority values (low|medium|high|urgent) pass through unchanged.
    """
    if not value:
        return ''
        
    # Convert to string and clean up
    value = str(value).lower().strip()
    
    # Map specific values to their CSS class equivalents
    status_mapping = {
        'created': 'pending',
        'assigned': 'in-progress',
        'in_progress': 'in-progress',
        'inprogress': 'in-progress',
        'completed': 'completed',
        'cancelled': 'cancelled',
        'pending': 'pending',
        'low': 'low',
        'medium': 'medium',
        'high': 'high',
        'urgent': 'urgent'
    }
    
    # Return mapped value if it exists, otherwise clean the string
    return status_mapping.get(value, value.replace('_', '-'))

@register.filter(name='abs')
def absolute_value(value):
    """
    Returns the absolute value of a number.
    Usage: {{ value|abs }}
    """
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value
    except Exception:
        return ''

@register.filter(name='order_last_update')
def order_last_update(order):
    """
    Returns the most recent timestamp for an order in priority:
    completed_at > cancelled_at > started_at > assigned_at > created_at
    Returns timezone-aware datetime
    """
    try:
        if not order:
            return None
            
        from django.utils import timezone
        
        for attr in ['completed_at', 'cancelled_at', 'started_at', 'assigned_at', 'created_at']:
            val = getattr(order, attr, None)
            if val:
                # Ensure the datetime is timezone-aware
                if timezone.is_naive(val):
                    return timezone.make_aware(val, timezone=timezone.get_current_timezone())
                return val
                
        # If no timestamp found, return current time as fallback
        return timezone.now()
        
    except Exception as e:
        import logging
        logging.error(f"Error in order_last_update: {str(e)}")
        return timezone.now() if 'timezone' in locals() else None

@register.filter(name='margin_percentage')
def margin_percentage(price: Union[float, int, str, Decimal], 
                    cost_price: Union[float, int, str, Decimal, None] = None) -> float:
    """
    Calculate the margin percentage between price and cost price.
    If called with two arguments: {{ price|margin_percentage:cost_price }}
    If called with one argument (expects a tuple/dict): {{ item|margin_percentage }}
    """
    try:
        # Handle case where price is a dictionary/object with price and cost_price attributes
        if cost_price is None and hasattr(price, 'get'):
            # Handle dict-like objects
            price_val = float(price.get('price', 0))
            cost_val = float(price.get('cost_price', 0))
        elif cost_price is None and hasattr(price, 'price') and hasattr(price, 'cost_price'):
            # Handle object with price and cost_price attributes
            price_val = float(price.price)
            cost_val = float(price.cost_price)
        else:
            # Handle two separate values
            price_val = float(price)
            cost_val = float(cost_price) if cost_price is not None else 0
            
        if price_val <= 0 or cost_val <= 0:
            return 0
            
        margin = ((price_val - cost_val) / price_val) * 100
        return round(margin, 2)
    except (ValueError, TypeError, AttributeError):
        return 0
    except Exception:
        return ''
