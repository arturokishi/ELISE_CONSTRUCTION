from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from home.models import Conversation, Message, UserProfile, QuoteRequest, Product, SupplierCategory
from django.db.models import Q
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import json
import unicodedata


def remove_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


# ---------------- HELPERS ---------------- #

def get_or_create_conversation(user1, user2):
    conversation = Conversation.objects.filter(
        participants=user1
    ).filter(
        participants=user2
    ).first()

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(user1, user2)

    return conversation


def serialize_message(msg, current_user):
    return {
        "id": msg.id,
        "sender": msg.sender.username,
        "content": msg.content,
        "timestamp": msg.timestamp.strftime("%I:%M %p • %b %d"),
        "is_sent": msg.sender == current_user
    }


# ---------------- MATERIAL CONFIG ---------------- #

MATERIAL_CONFIG = {
    "pintura":   {"slug": "paint",     "keywords": ["pintura", "paint"],            "productos": "pinturas, barnices y más"},
    "acero":     {"slug": "steel",     "keywords": ["acero", "steel"],              "productos": "varillas, perfiles y más"},
    "cemento":   {"slug": "cement",    "keywords": ["cemento", "cement"],           "productos": "cemento, mortero y más"},
    "aluminio":  {"slug": "aluminum",  "keywords": ["aluminio", "aluminum"],        "productos": "perfiles, láminas y más"},
    "vidrio":    {"slug": "glass",     "keywords": ["vidrio", "glass", "cristal"],  "productos": "vidrio, cristal y más"},
}


def get_supplier_greeting(material):
    config = MATERIAL_CONFIG.get(material)
    if not config:
        return "Hola 👋 ¿En qué te puedo ayudar hoy?"
    return (
        f"Hola 👋 Somos tu proveedor de {material}.\n\n"
        f"Puedes usar los botones en la parte superior para:\n\n"
        f"• 📄 Ver o descargar nuestro catálogo de productos\n"
        f"• 📋 Solicitar una cotización personalizada\n"
        f"• 💬 Conectar directamente con nosotros por WhatsApp\n\n"
        f"¡Estamos listos para atenderte!"
    )


def detect_material(text):
    """Returns material name (e.g. 'acero') if a keyword is found in text, else None."""
    clean = remove_accents(text.lower().strip())
    for material, config in MATERIAL_CONFIG.items():
        if any(kw in clean for kw in config["keywords"]):
            return material
    return None


def connect_client_to_suppliers(client, material):
    """
    Finds all suppliers for a given material slug via ManyToMany,
    creates QuoteRequests and sends greeting messages.
    Returns (suppliers_count, reply_message).
    """
    config = MATERIAL_CONFIG[material]
    slug = config["slug"]
    emoji = config["emoji"]

    suppliers = User.objects.filter(
        userprofile__role="supplier",
        userprofile__material_categories__slug=slug
    ).distinct()

    print(f"DEBUG: Found {suppliers.count()} {material} suppliers")

    if not suppliers.exists():
        return 0, f"No hay proveedores de {material} disponibles por el momento."

    for supplier in suppliers:
        try:
            quote, created = QuoteRequest.objects.get_or_create(
                client=client,
                supplier=supplier,
                defaults={"status": "pending"}
            )
            supplier_convo = get_or_create_conversation(client, supplier)
            Message.objects.create(
                conversation=supplier_convo,
                sender=supplier,
                content=get_supplier_greeting(material),
                timestamp=timezone.now()
            )
            print(f"DEBUG: Connected {client.username} with {supplier.username} ({material})")
        except Exception as e:
            print(f"DEBUG: Error connecting to supplier {supplier.username}: {e}")

    count = suppliers.count()
    return count, f"✅ Te he conectado con {count} proveedor(es) de {material}. {emoji}"


# ---------------- VIEWS ---------------- #

def elicebot_reply(message, user=None):
    print(f"DEBUG: elicebot_reply called with: {message}")
    text = remove_accents(message.lower().strip())

    # SALUDOS
    greetings = ["hola", "buenos dias", "buenas tardes", "buenas", "hi", "hello"]
    if any(greet in text for greet in greetings):
        username = user.username if user else ""
        return (
            f"¡Hola {username}! 😊 Puedo ayudarte a conectar con proveedores de materiales.\n\n"
            f"¿Qué material necesitas?\n"
            f"• Acero \n"
            f"• Pintura \n"
            f"• Cemento \n"
            f"• Aluminio \n"
            f"• Vidrio "
        )

    # COTIZACION
    if "cotizacion" in text or "quote" in text:
        return (
            "💡 Para solicitar cotización, dime el material que necesitas:\n"
            "acero, pintura, cemento, aluminio o vidrio."
        )

    # FALLBACK
    print("DEBUG: No keyword detected, using fallback")
    return (
        "No entendí tu mensaje 😅. Puedes escribirme el nombre del material:\n"
        "acero, pintura, cemento, aluminio o vidrio."
    )


@login_required
def chat(request):
    conversations = request.user.conversations.all().order_by("-updated_at")
    selected_conversation_id = request.GET.get("conversation")

    selected_conversation = None
    if selected_conversation_id:
        selected_conversation = conversations.filter(
            id=selected_conversation_id
        ).first()

    return render(request, "home/chat.html", {
        "conversations": conversations,
        "selected_conversation": selected_conversation,
    })


@login_required
def get_conversation(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    my_profile = request.user.userprofile
    other_profile = other_user.userprofile

    print(f"DEBUG: Current user: {request.user.username} (role: {my_profile.role})")
    print(f"DEBUG: Other user: {other_user.username} (role: {other_profile.role})")

    if my_profile.role == "client":
        if other_user.username == "elicebot":
            print("DEBUG: Allowed - chatting with bot")
        elif other_profile.role == "supplier":
            allowed = QuoteRequest.objects.filter(
                client=request.user,
                supplier=other_user,
                status__in=["pending", "accepted"]
            ).exists()
            if not allowed:
                return JsonResponse(
                    {"error": "No tienes una cotización activa con este proveedor."},
                    status=403
                )
        else:
            return JsonResponse(
                {"error": "No puedes enviar mensajes a este usuario."},
                status=403
            )

    conversation = get_or_create_conversation(request.user, other_user)

    messages = conversation.messages.all().order_by("-timestamp")[:15]
    messages = list(reversed(messages))

    return JsonResponse({
            "conversation_id": conversation.id,
            "messages": [serialize_message(msg, request.user) for msg in messages],
            "other_user": {
                "id": other_user.id,
                "username": other_user.username,
                "first_name": other_user.first_name,
                "last_name": other_user.last_name,
                "role": other_profile.role if other_profile else "client",
                "company": other_profile.company if other_profile else "",
                "whatsapp": other_profile.whatsapp_number if other_profile else "",
                "has_catalog": bool(other_profile.catalog_pdf) if other_profile else False,
            }
        })


@login_required
def send_message(request):
    bot_reply_id = None
    bot_reply_content = None

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    data = json.loads(request.body)
    user_id = data.get("user_id")
    content = data.get("content")

    other_user = get_object_or_404(User, id=user_id)
    text = content.lower().strip()
    print(f"DEBUG: Received message from {request.user.username}: '{text}'")

    conversation = get_or_create_conversation(request.user, other_user)

    msg = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        content=content,
        timestamp=timezone.now()
    )

    if other_user.username == "elicebot":
        print("DEBUG: Message is to the bot")

        material = detect_material(text)

        if material:
            print(f"DEBUG: Material detected: {material}")
            count, reply = connect_client_to_suppliers(request.user, material)
        else:
            print("DEBUG: No material detected, using elicebot_reply")
            reply = elicebot_reply(content, user=request.user)

        print(f"DEBUG: Bot reply: '{reply}'")

        try:
            bot_msg = Message.objects.create(
                conversation=conversation,
                sender=other_user,
                content=reply,
                timestamp=timezone.now()
            )
            print("DEBUG: Bot message saved")
            bot_reply_content = reply
            bot_reply_id = bot_msg.id
        except Exception as e:
            print(f"DEBUG: Error saving bot message: {e}")

    response_data = {"success": True, "message_id": msg.id}
    if bot_reply_content:
        response_data["bot_reply"] = bot_reply_content
        response_data["bot_reply_id"] = bot_reply_id

    return JsonResponse(response_data)


@login_required
def get_users(request):
    current_user = request.user
    current_profile = current_user.userprofile

    users = User.objects.exclude(id=current_user.id)

    if current_profile.role == 'client':
        supplier_ids = UserProfile.objects.filter(
            role='supplier'
        ).values_list('user_id', flat=True)

        bot_user = User.objects.filter(username='elicebot').first()
        user_filter = Q(id__in=supplier_ids)

        if bot_user:
            user_filter = user_filter | Q(id=bot_user.id)

        users = users.filter(user_filter)

    users_data = []

    for user in users:
        profile = UserProfile.objects.filter(user=user).first()

        conversation = Conversation.objects.filter(
            participants=current_user
        ).filter(
            participants=user
        ).first()

        last_message = None
        if conversation:
            last_msg = conversation.messages.last()
            if last_msg:
                last_message = last_msg.content[:50]

        categories = []
        if profile and profile.role == 'supplier':
            # Use ManyToMany SupplierCategory
            categories = list(
                profile.material_categories.values_list('name', flat=True)
            )

        if user.username == 'elicebot' and not profile:
            role = 'bot'
            company = 'Asistente Elice'
            avatar_color = '#9ca3af'
        else:
            role = profile.role if profile else 'client'
            company = profile.company if profile else ''
            avatar_color = profile.avatar_color if profile else '#fbbf24'

        users_data.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': role,
            'company': company,
            'avatar_color': avatar_color,
            'last_message': last_message,
            'is_bot': user.username == 'elicebot',
            'categories': categories,
            'whatsapp': profile.whatsapp_number if profile else '',
            'has_catalog': bool(profile.catalog_pdf) if profile else False,
        })

    return JsonResponse({'users': users_data})


@login_required
def get_conversation_by_id(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    other_user = conversation.participants.exclude(id=request.user.id).first()

    messages = conversation.messages.all().order_by("-timestamp")[:15]
    messages = list(reversed(messages))
    messages_data = [serialize_message(msg, request.user) for msg in messages]

    profile = UserProfile.objects.filter(user=other_user).first()

    return JsonResponse({
        "conversation_id": conversation.id,
        "other_user": {
            "id": other_user.id,
            "username": other_user.username,
            "first_name": other_user.first_name,
            "last_name": other_user.last_name,
            "role": profile.role if profile else "client",
            "company": profile.company if profile else "",
        },
        "messages": messages_data,
    })


@login_required
def get_quote_form(request, supplier_id):
    supplier = get_object_or_404(User, id=supplier_id)
    products = Product.objects.filter(supplier=supplier, is_active=True).select_related('category')

    form_data = {
        'supplier': {
            'id': supplier.id,
            'name': supplier.get_full_name() or supplier.username,
        },
        'categories': []
    }

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

        for option in product.options.all():
            product_data['options'].append({
                'name': option.name,
                'options': option.get_options_list(),
                'required': option.required
            })

        categories[cat_name].append(product_data)

    for cat_name, products_list in categories.items():
        form_data['categories'].append({
            'name': cat_name,
            'products': products_list
        })

    return JsonResponse(form_data)

@login_required
def get_supplier_catalog(request, supplier_id):
    supplier = get_object_or_404(User, id=supplier_id)
    profile = get_object_or_404(UserProfile, user=supplier)
    
    if not profile.catalog_pdf:
        return JsonResponse({"has_catalog": False})
    
    return JsonResponse({
        "has_catalog": True,
        "catalog_url": profile.catalog_pdf.url,
        "supplier_name": supplier.get_full_name() or supplier.username,
    })