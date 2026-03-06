from django.shortcuts import render

#Por ahora: 
from .pages import *
from ..views import *
# BOrrar luego

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

def pintura(request):
    return render(request, "home/pintura.html")

def andamios(request):
    return render(request, "home/andamios.html")

def materiales(request):
    """Materiales page"""
    return render(request, "home/materiales.html")
