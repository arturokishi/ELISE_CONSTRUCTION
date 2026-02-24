from django.shortcuts import render
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Order, OrderItem

from django.shortcuts import redirect, get_object_or_404
from .models import QuoteRequest



from .models import Conversation

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from .models import Conversation, Message, UserProfile

# home/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .forms import UserRegisterForm, UserProfileForm
from .models import UserProfile
import json
from home.models import Conversation, Message, UserProfile, ProductCategory, Product, ProductOption, QuoteRequest
from django.db.models import Q



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

    # CLIENT RULES
    if my_profile.role == "client":
        # Client can always talk to bot
        if other_user.username == "elicebot":
            print("DEBUG: Allowed - chatting with bot")
            # <-- FIX: This path needs to continue to the conversation logic below.
            # Do NOT return here. Just let the function proceed to fetch/create the conversation.

        # Client → Supplier allowed ONLY if quote is pending or accepted
        elif other_profile.role == "supplier":
            allowed = QuoteRequest.objects.filter(
                client=request.user,
                supplier=other_user,
                status__in=["pending", "accepted"]
            ).exists()
            if not allowed:
                print(f"DEBUG: BLOCKING - no active quote with supplier {other_user.username}")
                return JsonResponse(
                    {"error": "No tienes una cotización activa con este proveedor."},
                    status=403
                )
        else:
            # This blocks client from talking to other clients or unknown roles
            print(f"DEBUG: BLOCKING - cannot message user with role {other_profile.role}")
            return JsonResponse(
                {"error": "No puedes enviar mensajes a este usuario."},
                status=403
            )

    # SUPPLIER RULES (Add similar debug prints and ensure returns are correct)
    elif my_profile.role == "supplier":
        # ... your supplier logic ...
        # Make sure it either returns a 403 for disallowed cases,
        # or lets the function proceed for allowed cases.
        pass # Placeholder - replace with your actual logic

    # --- COMMON LOGIC FOR ALLOWED CASES ---
    # This part should only be reached if the user is allowed to chat.
    # For example: bot chats, or client-supplier with active quote, etc.

    # GET OR CREATE CONVERSATION
    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)

    messages = conversation.messages.all().order_by("timestamp")

    # <-- FIX: This is the critical return that was missing for the bot path
    return JsonResponse({
        "conversation_id": conversation.id,
        "messages": [
            {
                "id": msg.id,
                "sender": msg.sender.username,
                "content": msg.content,
                "timestamp": msg.timestamp.strftime("%I:%M %p • %b %d"),
                "is_sent": msg.sender == request.user
            }
            for msg in messages
        ],
        "other_user": { # It's helpful to return other user info too
            "id": other_user.id,
            "username": other_user.username,
            "first_name": other_user.first_name,
            "last_name": other_user.last_name,
        }
    })





@login_required
def send_message(request):

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    data = json.loads(request.body)
    user_id = data.get("user_id")
    content = data.get("content")

    other_user = get_object_or_404(User, id=user_id)

    my_profile = request.user.userprofile
    text = content.lower().strip()

    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)

    # Save user message
    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        content=content,
        timestamp=timezone.now()
    )

    # Initialize bot_reply variable
    bot_reply_content = None

    # BOT LOGIC
    if other_user.username == "elicebot":

        # STEP 1: Check for quote keywords
        if any(word in text for word in ["quote", "cotización"]):
            reply = elicebot_reply(content)

        # STEP 2: MATERIAL ROUTING - NOW SHOWS ALL SUPPLIERS
        elif "pintura" in text or "paint" in text:
            # Get ALL paint suppliers
            suppliers = User.objects.filter(
                userprofile__role="supplier",
                userprofile__material_category="paint"
            )
            
            if suppliers.exists():
                # Create conversations with ALL suppliers
                for supplier in suppliers:
                    quote = QuoteRequest.objects.create(
                        client=request.user,
                        supplier=supplier
                    )

                    supplier_convo = Conversation.objects.create()
                    supplier_convo.participants.add(request.user, supplier)

                    Message.objects.create(
                        conversation=supplier_convo,
                        sender=supplier,
                        content=get_supplier_greeting('pintura'),
                        timestamp=timezone.now()
                    )

                    # Send email notification to supplier
                    try:
                        send_supplier_notification(
                            supplier=supplier,
                            client=request.user,
                            material="pintura",
                            conversation_id=supplier_convo.id,
                            quote_id=quote.id
                        )
                        print(f"✅ Email notification sent to {supplier.email}")
                    except Exception as e:
                        print(f"❌ Email notification failed: {e}")

                reply = f"✅ Te he conectado con {suppliers.count()} proveedor(es) de pintura. Revisa tu lista de chats para ver todos. 🎨"
            else:
                reply = "Lo siento, no hay proveedores de pintura disponibles en este momento."

        elif "acero" in text or "steel" in text:
            # Get ALL steel suppliers
            suppliers = User.objects.filter(
                userprofile__role="supplier",
                userprofile__material_category="steel"
            )
            
            if suppliers.exists():
                for supplier in suppliers:
                    quote = QuoteRequest.objects.create(
                        client=request.user,
                        supplier=supplier
                    )

                    supplier_convo = Conversation.objects.create()
                    supplier_convo.participants.add(request.user, supplier)

                    Message.objects.create(
                        conversation=supplier_convo,
                        sender=supplier,
                        content=get_supplier_greeting('acero'),
                        timestamp=timezone.now()
                    )

                    try:
                        send_supplier_notification(
                            supplier=supplier,
                            client=request.user,
                            material="acero",
                            conversation_id=supplier_convo.id,
                            quote_id=quote.id
                        )
                    except Exception as e:
                        print(f"❌ Email notification failed: {e}")

                reply = f"✅ Te he conectado con {suppliers.count()} proveedor(es) de acero. Revisa tu lista de chats. 🔩"
            else:
                reply = "Lo siento, no hay proveedores de acero disponibles en este momento."

        elif "cemento" in text:
            # Get ALL cement suppliers
            suppliers = User.objects.filter(
                userprofile__role="supplier",
                userprofile__material_category="cement"
            )
            
            if suppliers.exists():
                for supplier in suppliers:
                    quote = QuoteRequest.objects.create(
                        client=request.user,
                        supplier=supplier
                    )

                    supplier_convo = Conversation.objects.create()
                    supplier_convo.participants.add(request.user, supplier)

                    Message.objects.create(
                        conversation=supplier_convo,
                        sender=supplier,
                        content=get_supplier_greeting('cemento'),
                        timestamp=timezone.now()
                    )

                    try:
                        send_supplier_notification(
                            supplier=supplier,
                            client=request.user,
                            material="cemento",
                            conversation_id=supplier_convo.id,
                            quote_id=quote.id
                        )
                    except Exception as e:
                        print(f"❌ Email notification failed: {e}")

                reply = f"✅ Te he conectado con {suppliers.count()} proveedor(es) de cemento. Revisa tu lista de chats. 🏗️"
            else:
                reply = "Lo siento, no hay proveedores de cemento disponibles en este momento."

        else:
            reply = elicebot_reply(content)

        # Save bot message
        Message.objects.create(
            conversation=conversation,
            sender=other_user,
            content=reply,
            timestamp=timezone.now()
        )
        
        # Store the reply to return to frontend
        bot_reply_content = reply

    # Return success AND bot reply if any
    response_data = {"success": True}
    if bot_reply_content:
        response_data["bot_reply"] = bot_reply_content
    
    return JsonResponse(response_data)







@login_required
def get_users(request):
    """Get users for sidebar - clients only see suppliers (plus the bot)"""
    current_user = request.user
    current_profile = current_user.userprofile
    
    users = User.objects.exclude(id=current_user.id)
    
    if current_profile.role == 'client':
        # Get all supplier users
        supplier_ids = UserProfile.objects.filter(role='supplier').values_list('user_id', flat=True)
        
        # Get the bot user
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
                last_message = last_msg.content[:50] + '...' if len(last_msg.content) > 50 else last_msg.content
        
        # Get product categories for suppliers
        categories = []
        if profile and profile.role == 'supplier':
            # Get all categories for this supplier's products
            from .models import Product
            categories = list(Product.objects.filter(
                supplier=user, 
                is_active=True
            ).values_list('category__name', flat=True).distinct())
        
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
            'categories': categories,  # Now categories are included!
        })
    
    return JsonResponse({'users': users_data})




# Auth Views
def custom_login(request):
    if request.user.is_authenticated:
        return redirect('home:home')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido {username}!')
                
                # Redirect to next page or home
                next_page = request.GET.get('next', 'home:home')
                return redirect(next_page)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'home/login.html', {'form': form})

def custom_logout(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión exitosamente.')
    return redirect('home:home')

def register(request):
    if request.user.is_authenticated:
        return redirect('home:home')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Only save User
            # <-- REMOVE UserProfile.objects.create(...) here
            
            # Optionally, log in the user automatically
            login(request, user)
            messages.success(request, f'¡Cuenta creada para {user.username}!')
            return redirect('home:home')
    else:
        form = UserRegisterForm()
    
    return render(request, 'home/register.html', {'form': form})


@login_required
def profile(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            
            # Update user info
            request.user.first_name = form.cleaned_data.get('first_name', '')
            request.user.last_name = form.cleaned_data.get('last_name', '')
            request.user.email = form.cleaned_data.get('email', '')
            request.user.save()
            
            messages.success(request, 'Perfil actualizado exitosamente.')
            return redirect('home:profile')
    else:
        form = UserProfileForm(initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'role': profile.role,
            'company': profile.company,
            'phone': profile.phone,
        })
    
    return render(request, 'home/profile.html', {'form': form, 'profile': profile})

@login_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu contraseña ha sido actualizada.')
            return redirect('home:profile')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'home/password_change.html', {'form': form})



from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import UserProfile, Conversation

@login_required
def chat_with_user(request, username):
    """
    Handles redirect to chat with another user.
    - Clients cannot chat directly with suppliers; must go through Elice bot first.
    - Ensures UserProfile exists for both users.
    """
    # Get the target user
    target_user = get_object_or_404(User, username=username)

    # Ensure both users have a profile
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'role': 'client'}
    )
    target_profile, created = UserProfile.objects.get_or_create(
        user=target_user,
        defaults={'role': 'client'}
    )

    # 🚫 Block direct client → supplier chat
    if profile.role == "client" and target_profile.role == "supplier":
        messages.error(
            request,
            "Debes solicitar una cotización primero a través de Elice."
        )
        return redirect('home:chat_with_user', username="elicebot")

    # Get or create conversation
    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=target_user
    ).first()

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, target_user)
        conversation.save()

        # Auto-greeting from Elice bot (only for new conversation)
        if target_user.username == "elicebot":
            Message.objects.create(
                conversation=conversation,
                sender=target_user,
                content="Hola 👋 Soy Elice, el asistente de Elice Construcción. ¿En qué puedo ayudarte hoy?",
                timestamp=timezone.now()
            )

    # Redirect to chat page with conversation
    return redirect(f"/chat/?conversation={conversation.id}")






@login_required
def get_conversation_by_id(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    other_user = conversation.participants.exclude(id=request.user.id).first()

    messages = conversation.messages.all().order_by("timestamp")

    messages_data = [
        {
            "id": msg.id,
            "sender": msg.sender.username,
            "sender_id": msg.sender.id,
            "content": msg.content,
            "timestamp": msg.timestamp.strftime("%I:%M %p • %b %d"),
            "is_sent": msg.sender == request.user,
        }
        for msg in messages
    ]

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


    


def elicebot_reply(user_message):

    text = user_message.lower().strip()

    if any(word in text for word in ["hi", "hello", "hola"]):
        return (
            "Hola 👋 Soy Elice.\n\n"
            "Escribe 'quote' o 'cotización' para comenzar una solicitud."
        )

    if any(word in text for word in ["quote", "cotización"]):
        return (
            "Perfecto 👍\n\n"
            "¿Qué material necesitas?\n"
            "• Pintura\n"
            "• Acero\n"
            "• Cemento"
        )

    return (
        "Puedo ayudarte con cotizaciones.\n"
        "Escribe 'quote' para comenzar."
    )




def send_supplier_notification(supplier, client, material):
    """Send email notification to supplier about new quote request"""
    
    subject = f"Nueva solicitud de cotización - {material}"
    
    html_message = render_to_string('emails/new_quote_notification.html', {
        'supplier': supplier,
        'client': client,
        'material': material,
        'date': timezone.now().strftime("%d/%m/%Y %H:%M"),
        'chat_link': f"http://127.0.0.1:8000/chat/?conversation={conversation.id}"
    })
    
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject,
        plain_message,
        DEFAULT_FROM_EMAIL,
        [supplier.email],
        html_message=html_message,
        fail_silently=False,
    )


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

def get_supplier_greeting(material):
    """Return appropriate greeting based on material type"""
    greetings = {
        'pintura': """Hola 👋 Somos tu proveedor de pintura.

**¿Cómo puedo ayudarte hoy?**

• Para ver nuestros productos disponibles, haz clic en el icono **📋** en la esquina superior derecha
• Ahí encontrarás: colores, acabados y precios
• Selecciona el producto, especifica cantidad y envíanos tu solicitud

¡Estamos listos para cotizarte! 🎨""",
        
        'acero': """Hola 👋 Somos tu proveedor de acero.

**¿Cómo puedo ayudarte hoy?**

• Para ver nuestros productos disponibles, haz clic en el icono **📋** en la esquina superior derecha
• Ahí encontrarás: varillas, perfiles y más
• Selecciona el producto, especifica medidas y envíanos tu solicitud

¡Estamos listos para cotizarte! 🔩""",
        
        'cemento': """Hola 👋 Somos tu proveedor de cemento.

**¿Cómo puedo ayudarte hoy?**

• Para ver nuestros productos disponibles, haz clic en el icono **📋** en la esquina superior derecha
• Ahí encontrarás: cemento, blocks, mortero y más
• Selecciona el producto, especifica cantidad y envíanos tu solicitud

¡Estamos listos para cotizarte! 🏗️"""
    }
    
    return greetings.get(material, "Hola 👋 ¿En qué podemos ayudarte?")