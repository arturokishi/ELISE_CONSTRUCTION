
from django.urls import path
from . import views

app_name = "home"

urlpatterns = [
    path("", views.home, name="home"),
    path("productos/", views.productos, name="productos"),
    path("productos/cemento/", views.cemento, name="cemento"),
    path("industrias/", views.industrias, name="industrias"),
    path("nosotros/", views.nosotros, name="nosotros"),
    path("contacto/", views.contacto, name="contacto"),
    path("api/create-order/", views.create_order, name="create_order"),

]

