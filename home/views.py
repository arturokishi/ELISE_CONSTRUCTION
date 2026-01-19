from django.shortcuts import render


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Order, OrderItem



def home(request):
    return render(request, "home/home.html")

def productos(request):
    return render(request, "home/productos.html")

def industrias(request):
    return render(request, "home/industrias.html")

def nosotros(request):
    return render(request, "home/nosotros.html")

def contacto(request):
    return render(request, "home/contacto.html")

def cemento(request):
    return render(request, "home/cemento.html")


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

