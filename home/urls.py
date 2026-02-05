# home/urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

# home/urls.py
from django.urls import path
from . import views

# Add this line:
app_name = 'home'  # ← This creates the 'home' namespace

urlpatterns = [
    path("", views.home, name="home"),
    path("productos/", views.productos, name="productos"),
    path("productos/cemento/", views.cemento, name="cemento"),
    path("industrias/", views.industrias, name="industrias"),
    path("nosotros/", views.nosotros, name="nosotros"),
    path("contacto/", views.contacto, name="contacto"),
    path("api/create-order/", views.create_order, name="create_order"),
    path("productos/pintura/", views.pintura, name="pintura"),
    path("productos/andamios/", views.andamios, name="andamios"),
    
    # Auth URLs
    path("login/", views.custom_login, name="login"),
    path("logout/", views.custom_logout, name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("password-change/", views.password_change, name="password_change"),
    
    # Chat URLs
    path("chat/", views.chat, name="chat"),
    path("chat/conversation/<int:user_id>/", views.get_conversation, name="get_conversation"),
    path("chat/send/", views.send_message, name="send_message"),
    path("chat/users/", views.get_users, name="get_users"),
]





