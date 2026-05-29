from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from home.models import Conversation, Message, UserProfile, QuoteRequest, Product, Category, Supplier
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
# Ahora los slugs apuntan a Category.slug en lugar de SupplierCategory.slug
 
MATERIAL_CONFIG = {
    "pintura":   {"slug": "pinturas-y-recubrimientos",  "emoji": "🎨", "keywords": ["pintura", "paint"],           "productos": "pinturas, barnices y más"},
    "acero":     {"slug": "acero-y-perfiles",           "emoji": "🔩", "keywords": ["acero", "steel"],             "productos": "varillas, perfiles y más"},
    "cemento":   {"slug": "cemento",                    "emoji": "🏗️", "keywords": ["cemento", "cement"],          "productos": "cemento, mortero y más"},
    "aluminio":  {"slug": "vidrio-y-aluminio",          "emoji": "🪟", "keywords": ["aluminio", "aluminum"],       "productos": "perfiles, láminas y más"},
    "vidrio":    {"slug": "vidrio-y-aluminio",          "emoji": "🪞", "keywords": ["vidrio", "glass", "cristal"], "productos": "vidrio, cristal y más"},
    
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
    Finds all suppliers for a given material via Supplier.categories (M2M to Category).
    Creates QuoteRequests and sends greeting messages.
    Returns (suppliers_count, reply_message).
    """
    config = MATERIAL_CONFIG[material]
    slug = config["slug"]
    emoji = config["emoji"]
 
    # Suppliers are Users that have a Supplier profile with this category slug
    supplier_users = User.objects.filter(
        supplier_profile__categories__slug=slug,
        supplier_profile__is_active=True,
    ).distinct()
 
    print(f"DEBUG: Found {supplier_users.count()} {material} suppliers")
 
    if not supplier_users.exists():
        return 0, f"No hay proveedores de {material} disponibles por el momento."
 
    for supplier in supplier_users:
        try:
            supplier_convo = get_or_create_conversation(client, supplier)
            quote, created = QuoteRequest.objects.get_or_create(
                client=client,
                supplier=supplier,
                defaults={
                    "status": "pending",
                    "conversation": supplier_convo,
                }
            )
            if not created and not quote.conversation:
                quote.conversation = supplier_convo
                quote.save(update_fields=["conversation"])
            Message.objects.create(
                conversation=supplier_convo,
                sender=supplier,
                content=get_supplier_greeting(material),
                timestamp=timezone.now()
            )
            print(f"DEBUG: Connected {client.username} with {supplier.username} ({material})")
        except Exception as e:
            print(f"DEBUG: Error connecting to supplier {supplier.username}: {e}")
 
    count = supplier_users.count()
    return count, f"✅ Te he conectado con {count} proveedor(es) de {material}. {emoji}"
 
 
# ---------------- VIEWS ---------------- #
 
def elicebot_reply(message, user=None):
    print(f"DEBUG: elicebot_reply called with: {message}")
    text = remove_accents(message.lower().strip())
 
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
 
    if "cotizacion" in text or "quote" in text:
        return (
            "💡 Para solicitar cotización, dime el material que necesitas:\n"
            "acero, pintura, cemento, aluminio o vidrio."
        )
 
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
                status__in=["pending", "accepted", "quoted"]
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

    # Get active quote — from client's or supplier's perspective
    active_quote = None
    if request.user.userprofile.role == 'client':
        quote = QuoteRequest.objects.filter(
            client=request.user,
            supplier=other_user,
        ).order_by('-created_at').first()
    elif request.user.userprofile.role == 'supplier':
        quote = QuoteRequest.objects.filter(
            supplier=request.user,
            client=other_user,
        ).order_by('-created_at').first()
    else:
        quote = None

    if quote:
        active_quote = {
            'id': quote.id,
            'status': quote.status,
            'payment_status': quote.payment_status,
            'quoted_price': float(quote.quoted_price) if quote.quoted_price else None,
            'product_name': quote.product_name,
        }

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
        },
        "active_quote": active_quote,
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

    elif current_profile.role == 'supplier':
        # Suppliers only see clients they have an active quote with
        client_ids = QuoteRequest.objects.filter(
            supplier=current_user
        ).values_list('client_id', flat=True).distinct()

        users = users.filter(
            id__in=client_ids,
            userprofile__role='client'
        )
 
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
 
        # Categorías desde el nuevo modelo Supplier
        categories = []
        if profile and profile.role == 'supplier':
            try:
                categories = list(
                    user.supplier_profile.categories.values_list('name', flat=True)
                )
            except Supplier.DoesNotExist:
                categories = []
 
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

    # Get active quote — from client's or supplier's perspective
    active_quote = None
    if request.user.userprofile.role == 'client':
        quote = QuoteRequest.objects.filter(
            client=request.user,
            supplier=other_user,
        ).order_by('-created_at').first()
    elif request.user.userprofile.role == 'supplier':
        quote = QuoteRequest.objects.filter(
            supplier=request.user,
            client=other_user,
        ).order_by('-created_at').first()
    else:
        quote = None

    if quote:
        active_quote = {
            'id': quote.id,
            'status': quote.status,
            'payment_status': quote.payment_status,
            'quoted_price': float(quote.quoted_price) if quote.quoted_price else None,
            'product_name': quote.product_name,
        }

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
        "active_quote": active_quote,
    })
 
 
 
@login_required
def reply_quote_price(request, quote_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    if request.user.userprofile.role != 'supplier':
        return JsonResponse({'error': 'Only suppliers can reply with a price'}, status=403)

    data = json.loads(request.body)
    price = data.get('price')
    notes = data.get('notes', '')
    valid_until = data.get('valid_until')

    if not price:
        return JsonResponse({'error': 'Price is required'}, status=400)

    try:
        quote = QuoteRequest.objects.get(
            id=quote_id,
            supplier=request.user
        )
    except QuoteRequest.DoesNotExist:
        return JsonResponse({'error': 'Quote not found'}, status=404)

    # Update the quote with the supplier's price
    quote.quoted_price = price
    quote.supplier_notes = notes
    quote.status = 'quoted'
    if valid_until:
        from datetime import date
        quote.valid_until = valid_until
    quote.save(update_fields=['quoted_price', 'supplier_notes', 'status', 'valid_until'])

    # Send a message in the conversation so the client sees it
    conversation = quote.conversation
    if conversation:
        price_message = (
            f"💰 PRECIO COTIZADO\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Producto: {quote.product_name}\n"
            f"Precio: ${float(quote.quoted_price):,.2f}\n"
            f"{f'Válido hasta: {quote.valid_until}' if quote.valid_until else ''}\n"
            f"Notas: {notes or 'Ninguna'}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Puedes proceder al pago desde tu chat."
        )
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=price_message,
            timestamp=timezone.now()
        )

    return JsonResponse({
        'success': True,
        'quote_id': quote.id,
        'quoted_price': float(quote.quoted_price),
    })
def get_quote_form(request, supplier_id):
    supplier_user = get_object_or_404(User, id=supplier_id)
 
    # Productos donde este usuario es uno de los suppliers (M2M)
    products = Product.objects.filter(
        suppliers__user=supplier_user,
        is_active=True
    ).select_related('category').prefetch_related('specifications__field')
 
    form_data = {
        'supplier': {
            'id': supplier_user.id,
            'name': supplier_user.get_full_name() or supplier_user.username,
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
            'base_price': float(product.base_price) if product.base_price else None,
            'unit': product.unit,
            'image_url': product.main_image.url if product.main_image else None,            'specifications': []
        }
 
        # Especificaciones dinámicas en lugar de ProductOption
        for spec in product.specifications.all():
            product_data['specifications'].append({
                'name': spec.field.name,
                'value': spec.value,
                'field_type': spec.field.field_type,
                'unit': spec.field.unit,
            })
 
        categories[cat_name].append(product_data)
 
    for cat_name, products_list in categories.items():
        form_data['categories'].append({
            'name': cat_name,
            'products': products_list
        })
 
    return JsonResponse(form_data)
 
 
@login_required
def update_quote(request, quote_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    if request.user.userprofile.role != "client":
        return JsonResponse({"error": "Only clients can update quotes"}, status=403)

    data = json.loads(request.body)
    product_name = data.get("product_name", "").strip()
    quantity     = data.get("quantity", 1)
    notes        = data.get("notes", "").strip()
    product_id   = data.get("product_id")

    if not product_name:
        return JsonResponse({"error": "product_name is required"}, status=400)

    try:
        quote = QuoteRequest.objects.get(id=quote_id, client=request.user)
    except QuoteRequest.DoesNotExist:
        return JsonResponse({"error": "Quote not found"}, status=404)

    product_details = {"quantity": quantity}
    if product_id:
        try:
            product = Product.objects.get(id=product_id)
            product_details.update({
                "product_id": product.id,
                "unit": product.unit,
                "base_price": float(product.base_price) if product.base_price else None,
            })
        except Product.DoesNotExist:
            pass

    quote.product_name    = product_name
    quote.client_notes    = notes
    quote.product_details = product_details
    quote.save(update_fields=["product_name", "client_notes", "product_details"])

    return JsonResponse({
        "success": True,
        "quote_id": quote.id,
        "product_name": quote.product_name,
    })


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