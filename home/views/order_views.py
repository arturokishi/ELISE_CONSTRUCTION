from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.models import User

from home.models import Product  

@csrf_exempt
def create_order(request):
    if request.method == "POST":
        data = json.loads(request.body)

        order = Order.objects.create(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            total=data["total"]
        )

        for item in data["items"]:
            OrderItem.objects.create(
                order=order,
                product_name=item["name"],
                price=item["price"]
            )

        return JsonResponse({"success": True})
    
    @login_required
    def get_quote_form(request, supplier_id):
     """Return the quote form structure for a specific supplier"""
    supplier = get_object_or_404(User, id=supplier_id)
    products = Product.objects.filter(supplier=supplier, is_active=True).select_related('category')
    
    form_data = {
        'supplier': {
            'id': supplier.id,
            'name': supplier.get_full_name() or supplier.username,
        },
        'categories': []
    }
    
    # Group by category
    categories = {}
    for product in products:
        cat_name = product.category.name if product.category else 'Otros'
        if cat_name not in categories:
            categories[cat_name] = []
        
        product_data = {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'base_price': float(product.base_price),
            'unit': product.unit,
            'options': []
        }
        
        # Add product options
        for option in product.options.all():
            product_data['options'].append({
                'name': option.name,
                'options': option.get_options_list(),
                'required': option.required
            })
        
        categories[cat_name].append(product_data)
    
    # Convert to list for template
    for cat_name, products in categories.items():
        form_data['categories'].append({
            'name': cat_name,
            'products': products
        })
    
    return JsonResponse(form_data)