from django.shortcuts import render


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Order, OrderItem

from django.shortcuts import redirect, get_object_or_404


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
    """Get or create conversation with another user"""
    other_user = get_object_or_404(User, id=user_id)

    # Find existing conversation
    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    # Create new conversation if it doesn't exist
    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)
        conversation.save()

        # Auto-greeting from Elice bot (ONLY once)
        if other_user.username == "elicebot":
            Message.objects.create(
                conversation=conversation,
                sender=other_user,
                content="Hola 👋 Soy Elice, el asistente de Recal. ¿En qué puedo ayudarte hoy?",
                timestamp=timezone.now()
            )

    # Get messages
    messages = conversation.messages.all().order_by("timestamp")

    # Mark messages as read
    conversation.messages.filter(
        sender=other_user,
        is_read=False
    ).update(is_read=True)

    messages_data = []
    for msg in messages:
        messages_data.append({
            "id": msg.id,
            "sender": msg.sender.username,
            "sender_id": msg.sender.id,
            "content": msg.content,
            "file_name": msg.file_name,
            "timestamp": msg.timestamp.strftime("%I:%M %p • %b %d"),
            "is_sent": msg.sender.id == request.user.id,
        })

    other_profile = UserProfile.objects.filter(user=other_user).first()

    return JsonResponse({
        "conversation_id": conversation.id,
        "other_user": {
            "id": other_user.id,
            "username": other_user.username,
            "first_name": other_user.first_name,
            "last_name": other_user.last_name,
            "role": other_profile.role if other_profile else "client",
            "company": other_profile.company if other_profile else "",
        },
        "messages": messages_data,
    })


@login_required
def send_message(request):
    """Send a new message"""
    if request.method == "POST":
        data = json.loads(request.body)
        user_id = data.get("user_id")
        content = data.get("content")

        if not user_id or not content:
            return JsonResponse({"error": "Missing data"}, status=400)

        other_user = get_object_or_404(User, id=user_id)

        # Get or create conversation
        conversation = Conversation.objects.filter(
            participants=request.user
        ).filter(
            participants=other_user
        ).first()

        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(request.user, other_user)

        # Create user message
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
            timestamp=timezone.now()
        )

        # Bot auto-reply
        if other_user.username == "elicebot":
            bot_reply = elicebot_reply(content)

            Message.objects.create(
                conversation=conversation,
                sender=other_user,
                content=bot_reply,
                timestamp=timezone.now()
            )

        conversation.updated_at = timezone.now()
        conversation.save()

        return JsonResponse({
            "success": True,
            "message_id": message.id,
            "timestamp": message.timestamp.strftime("%I:%M %p • %b %d"),
        })

    return JsonResponse({"error": "Invalid method"}, status=405)


@login_required
def get_users(request):
    """Get all users for sidebar"""
    users = User.objects.exclude(id=request.user.id)
    users_data = []
    
    for user in users:
        profile = UserProfile.objects.filter(user=user).first()
        
        # Get last message with this user
        conversation = Conversation.objects.filter(
            participants=request.user
        ).filter(
            participants=user
        ).first()
        
        last_message = None
        if conversation:
            last_msg = conversation.messages.last()
            if last_msg:
                last_message = last_msg.content[:50] + '...' if len(last_msg.content) > 50 else last_msg.content
        
        users_data.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': profile.role if profile else 'client',
            'company': profile.company if profile else '',
            'avatar_color': profile.avatar_color if profile else '#fbbf24',
            'last_message': last_message,
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
        # Redirect to bot chat instead
        return redirect('home:chat_with_user', username="elicebot")

    # Get or create conversation
    conversation = (
        Conversation.objects
        .filter(participants=request.user)
        .filter(participants=target_user)
        .first()
    )

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, target_user)
        conversation.save()

    # ✅ Redirect to the chat page with conversation
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
    """
    Simple rule-based chatbot for Elice.
    Returns responses based on keywords and phrases.
    """

    text = user_message.lower().strip()

    # --- Greetings ---
    if any(word in text for word in ["hi", "hello", "hola", "buenos días", "buenas tardes"]):
        return (
            "Hola 👋 Soy Elice, el asistente de Elice Construcción.\n\n"
            "Puedo ayudarte con cotizaciones, información de productos "
            "o ponerte en contacto con nuestro equipo."
        )

    # --- Asking for quotes / prices ---
    if any(word in text for word in ["quote", "cotización", "precio", "price", "valor", "cost"]):
        return (
            "Perfecto 📄\n\n"
            "Para preparar tu cotización necesito:\n"
            "• Producto o servicio\n"
            "• Cantidad\n"
            "• Empresa (opcional)\n\n"
            "Puedes escribirlo aquí mismo y te ayudaré."
        )

    # --- Contact / email ---
    if any(word in text for word in ["email", "correo", "contact", "contacto", "asistente"]):
        return (
            "Genial 👍\n\n"
            "Un asesor humano revisará tu solicitud y "
            "te contactará por correo lo antes posible."
        )

    # --- Thanks / appreciation ---
    if any(word in text for word in ["thanks", "gracias", "thank you", "ok", "vale"]):
        return "¡De nada! 😊 ¿Quieres que te ayude con otra cosa?"

    # --- Small talk or fallback ---
    if any(word in text for word in ["how are you", "qué tal", "cómo estás"]):
        return "Estoy bien, gracias por preguntar 😊. ¿En qué puedo ayudarte hoy?"

    # --- Default fallback ---
    return (
        "Gracias por tu mensaje 😊\n\n"
        "Puedo ayudarte con:\n"
        "• Cotizaciones\n"
        "• Información general sobre productos\n"
        "• Contactar a un asesor\n\n"
        "¿Qué necesitas?"
    )



