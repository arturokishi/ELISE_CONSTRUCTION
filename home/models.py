from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models.signals import pre_delete
from django.core.exceptions import PermissionDenied



class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def get_other_participant(self, current_user):
        return self.participants.exclude(id=current_user.id).first()

    def __str__(self):
        participant_names = [user.username for user in self.participants.all()]
        return f"Conversation: {' & '.join(participant_names)}"


class Order(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    conversation = models.ForeignKey(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders"
    )

    def __str__(self):
        return f"Order #{self.id} - {self.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name="items",
        on_delete=models.CASCADE
    )
    product_name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.product_name


# models.py

class UserProfile(models.Model):

    ROLE_CHOICES = (
        ('client', 'Cliente'),
        ('supplier', 'Proveedor'),
        ('admin', 'Administrador'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='client'
    )

    company = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar_color = models.CharField(max_length=7, default='#fbbf24')

    # ✅ Add this field (for supplier material assignment)
    material_category = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"




# --- PLACE THE SIGNAL HERE, BELOW THE MODEL ---
from django.db.models.signals import post_save
from django.dispatch import receiver




class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}..."





    
class QuoteRequest(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )

    client = models.ForeignKey(
        User,
        related_name="client_quotes",
        on_delete=models.CASCADE
    )

    supplier = models.ForeignKey(
        User,
        related_name="supplier_quotes",
        on_delete=models.CASCADE
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client.username} → {self.supplier.username} ({self.status})"
# Add to the VERY BOTTOM of home/models.py


@receiver(pre_delete, sender=User)
def protect_bot_user(sender, instance, **kwargs):
    """Prevent deletion of the bot user"""
    if instance.username == "elicebot":
        raise PermissionDenied("The Elice bot user cannot be deleted.")
    
class ProductCategory(models.Model):
    """Categories like Pintura, Acero, Cemento, etc."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Emoji or icon name")
    order = models.IntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Product Categories"
        ordering = ['order']
    
    def __str__(self):
        return self.name

class Product(models.Model):
    """Products that suppliers offer"""
    supplier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, default="unidad", help_text="e.g., litro, kg, pieza")
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} - ${self.base_price}"

class ProductOption(models.Model):
    """Optional specifications for products (color, size, etc.)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='options')
    name = models.CharField(max_length=100)  # e.g., "Color", "Acabado", "Tamaño"
    options = models.TextField(help_text="Comma-separated options")  # e.g., "Blanco, Beige, Gris"
    required = models.BooleanField(default=False)
    
    def get_options_list(self):
        return [opt.strip() for opt in self.options.split(',')]
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"

class QuoteRequest(models.Model):
    """Store quote requests from clients"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('quoted', 'Quoted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('countered', 'Counter Offered'),
    )
    
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quote_requests')
    supplier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_quotes')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, null=True)
    
    # Product details (snapshot at time of request)
    product_name = models.CharField(max_length=200)
    product_details = models.JSONField(default=dict)  # Stores quantity, options, etc.
    client_notes = models.TextField(blank=True)
    
    # Quote response
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier_notes = models.TextField(blank=True)
    valid_until = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Quote #{self.id} - {self.client.username} → {self.supplier.username}"