# home/urls.py
from django.urls import path
from .views.pages import home, productos, cemento, industrias, nosotros, contacto, pintura, andamios, materiales
from .views.auth_views import custom_login, custom_logout, register, profile, password_change
from .views.chat_views import (
    chat,
    get_conversation,
    send_message,
    get_users,
    get_conversation_by_id,
    get_quote_form,
    get_supplier_catalog
)
from .views.order_views import create_order
app_name = 'home'

urlpatterns = [
    # Main pages
    path("", home, name="home"),
    path("productos/", productos, name="productos"),
    path("productos/cemento/", cemento, name="cemento"),
    path("industrias/", industrias, name="industrias"),
    path("nosotros/", nosotros, name="nosotros"),
    path("contacto/", contacto, name="contacto"),
    path("productos/pintura/", pintura, name="pintura"),
    path("productos/andamios/", andamios, name="andamios"),
    path("materiales/", materiales, name="materiales"),

    # Orders / API
    path("api/create-order/", create_order, name="create_order"),

    # Auth
    path("login/", custom_login, name="login"),
    path("logout/", custom_logout, name="logout"),
    path("register/", register, name="register"),
    path("profile/", profile, name="profile"),
    path("password-change/", password_change, name="password_change"),

    # Chat
    path("chat/", chat, name="chat"),
    path("chat/conversation/<int:user_id>/", get_conversation, name="get_conversation"),
    path("chat/send/", send_message, name="send_message"),
    path("chat/users/", get_users, name="get_users"),
    path("chat/conversation/by-id/<int:conversation_id>/", get_conversation_by_id, name="get_conversation_by_id"),
    path("chat/quote-form/<int:supplier_id>/", get_quote_form, name="quote_form"),
    path('chat/supplier-catalog/<int:supplier_id>/', get_supplier_catalog, name='supplier_catalog'),
]