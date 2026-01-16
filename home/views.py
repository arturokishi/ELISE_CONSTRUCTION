from django.shortcuts import render

def home(request):
    return render(request, "home/home.html")


from django.shortcuts import render

def home(request):
    return render(request, "home/home.html")


def productos(request):
    return render(request, "home/productos.html")


def industrias(request):
    return render(request, "industrias.html")

def nosotros(request):
    return render(request, "nosotros.html")

def contacto(request):
    return render(request, "contacto.html")
