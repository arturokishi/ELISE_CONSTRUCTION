from django.shortcuts import render

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


