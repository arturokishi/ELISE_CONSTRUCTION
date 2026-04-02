from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import PermissionDenied
 
 
# ─────────────────────────────────────────────
# CHAT & MESSAGING
# ─────────────────────────────────────────────
 
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
 
 
class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
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
 
 
# ─────────────────────────────────────────────
# ORDERS
# ─────────────────────────────────────────────
 
class Order(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    conversation = models.ForeignKey(
        Conversation, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
 
    def __str__(self):
        return f"Order #{self.id} - {self.name}"
 
 
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product_name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
 
    def __str__(self):
        return self.product_name
 
 
# ─────────────────────────────────────────────
# CATEGORIES (árbol jerárquico autorreferencial)
# ─────────────────────────────────────────────
 
class Category(models.Model):
    """
    Árbol de categorías de N niveles usando modelo autorreferencial.
 
    Ejemplos de uso:
      Nivel 1 (madre):  parent=None  → "Pinturas, Recubrimientos y Herramientas"
      Nivel 2 (familia): parent=nivel1 → "Pinturas Arquitectónicas"
      Nivel 3 (sub):    parent=nivel2 → "Pintura acrílica interior"
    """
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True, help_text="Emoji o nombre de ícono")
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['order', 'name']
 
    def __str__(self):
        if self.parent:
            return f"{self.parent} → {self.name}"
        return self.name
 
    @property
    def level(self):
        """Retorna el nivel en el árbol (0 = raíz)."""
        level = 0
        node = self
        while node.parent:
            level += 1
            node = node.parent
        return level
 
    @property
    def ancestors(self):
        """Retorna lista de ancestros desde la raíz."""
        path = []
        node = self
        while node.parent:
            path.insert(0, node.parent)
            node = node.parent
        return path
 
    def get_descendants(self):
        """Retorna todos los descendientes recursivamente."""
        result = []
        for child in self.children.filter(is_active=True):
            result.append(child)
            result.extend(child.get_descendants())
        return result
 
 
# ─────────────────────────────────────────────
# BRANDS (marcas transversales)
# ─────────────────────────────────────────────
 
class Brand(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['name']
 
    def __str__(self):
        return self.name
 
 
# ─────────────────────────────────────────────
# USER PROFILE & SUPPLIER
# ─────────────────────────────────────────────
 
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('client', 'Cliente'),
        ('supplier', 'Proveedor'),
        ('admin', 'Administrador'),
    )
 
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    company = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar_color = models.CharField(max_length=7, default='#fbbf24')
    whatsapp_number = models.CharField(
        max_length=20, blank=True,
        help_text="Número internacional sin espacios, ej: 521234567890"
    )
    catalog_pdf = models.FileField(
        upload_to='catalogs/', blank=True, null=True,
        help_text="Catálogo del proveedor en PDF (opcional)"
    )
 
    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
 
 
class Supplier(models.Model):
    """
    Perfil extendido para usuarios con rol 'supplier'.
    Permite registrar información detallada del proveedor.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='supplier_profile'
    )
    # Información de contacto
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
 
    # Ubicación
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
 
    # Negocio
    description = models.TextField(blank=True, help_text="Descripción del proveedor")
    logo = models.ImageField(upload_to='suppliers/logos/', blank=True, null=True)
 
    # Categorías que maneja (usando el nuevo árbol)
    categories = models.ManyToManyField(
        Category, blank=True, related_name='suppliers',
        help_text="Categorías de productos que ofrece este proveedor"
    )
 
    # Marcas que distribuye
    brands = models.ManyToManyField(
        Brand, blank=True, related_name='suppliers'
    )
 
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['user__username']
 
    def __str__(self):
        return self.user.userprofile.company or self.user.username
 
 
# ─────────────────────────────────────────────
# SPECIFICATION TEMPLATES (atributos dinámicos)
# ─────────────────────────────────────────────
 
class SpecificationTemplate(models.Model):
    """
    Plantilla de especificaciones asociada a una categoría.
    Ejemplo: La categoría "Pintura acrílica" tiene una plantilla con campos:
      - Color (select)
      - Acabado (select)
      - Rendimiento (number + unidad)
      - Base química (text)
    """
    category = models.OneToOneField(
        Category, on_delete=models.CASCADE, related_name='spec_template'
    )
    name = models.CharField(max_length=200, help_text="Nombre descriptivo de la plantilla")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    def __str__(self):
        return f"Plantilla: {self.category.name}"
 
 
class SpecificationField(models.Model):
    """
    Campo individual dentro de una plantilla de especificaciones.
    """
    FIELD_TYPES = (
        ('text', 'Texto libre'),
        ('number', 'Número'),
        ('select', 'Selección única'),
        ('multiselect', 'Selección múltiple'),
        ('boolean', 'Sí / No'),
        ('url', 'URL / Enlace'),
    )
 
    template = models.ForeignKey(
        SpecificationTemplate, on_delete=models.CASCADE, related_name='fields'
    )
    name = models.CharField(max_length=150, help_text="Nombre del campo, ej: 'Color', 'Diámetro'")
    key = models.SlugField(max_length=150, help_text="Clave interna sin espacios, ej: 'color', 'diametro'")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    unit = models.CharField(max_length=50, blank=True, help_text="Unidad de medida, ej: mm, kg, m²")
    choices = models.TextField(
        blank=True,
        help_text="Opciones separadas por coma (solo para select/multiselect), ej: Blanco, Gris, Negro"
    )
    is_required = models.BooleanField(default=False)
    is_filterable = models.BooleanField(
        default=False, help_text="¿Debe mostrarse como filtro en el listado?"
    )
    order = models.PositiveIntegerField(default=0)
 
    class Meta:
        ordering = ['order', 'name']
        unique_together = [['template', 'key']]
 
    def get_choices_list(self):
        if self.choices:
            return [c.strip() for c in self.choices.split(',')]
        return []
 
    def __str__(self):
        return f"{self.template.category.name} → {self.name} ({self.field_type})"
 
 
# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────
 
class Product(models.Model):
    """
    Producto del catálogo. Puede pertenecer a múltiples proveedores y marcas.
    Sus especificaciones se almacenan dinámicamente en ProductSpecification.
    """
    # Relaciones principales
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    suppliers = models.ManyToManyField(
        Supplier, related_name='products', blank=True
    )
    brands = models.ManyToManyField(
        Brand, related_name='products', blank=True
    )
 
    # Datos básicos
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, default="unidad", help_text="ej: litro, kg, pieza, m²")
 
    # Archivos
    main_image = models.ImageField(upload_to='products/images/', blank=True, null=True)
    technical_sheet = models.FileField(
        upload_to='products/docs/', blank=True, null=True,
        help_text="Ficha técnica en PDF"
    )
 
    # Control
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False, help_text="Mostrar en la landing page")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['category', 'name']
 
    def __str__(self):
        return self.name
 
 
class ProductImage(models.Model):
    """Imágenes adicionales de un producto."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/images/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
 
    class Meta:
        ordering = ['order']
 
    def __str__(self):
        return f"{self.product.name} - imagen {self.order}"
 
 
class ProductSpecification(models.Model):
    """
    Valor concreto de una especificación para un producto específico.
    Relaciona Product + SpecificationField + valor.
    """
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='specifications'
    )
    field = models.ForeignKey(
        SpecificationField, on_delete=models.CASCADE, related_name='values'
    )
    value = models.TextField()
 
    class Meta:
        unique_together = [['product', 'field']]
 
    def __str__(self):
        return f"{self.product.name} | {self.field.name}: {self.value}"
 
 
# ─────────────────────────────────────────────
# QUOTES
# ─────────────────────────────────────────────
 
class QuoteRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('quoted', 'Cotizado'),
        ('accepted', 'Aceptado'),
        ('rejected', 'Rechazado'),
        ('countered', 'Contraoferta'),
    )
 
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quote_requests')
    supplier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_quotes')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, null=True)
 
    # Snapshot del producto al momento de la solicitud
    product_name = models.CharField(max_length=200)
    product_details = models.JSONField(default=dict)
    client_notes = models.TextField(blank=True)
 
    # Respuesta del proveedor
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier_notes = models.TextField(blank=True)
    valid_until = models.DateField(null=True, blank=True)
 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    def __str__(self):
        return f"Quote #{self.id} - {self.client.username} → {self.supplier.username}"
 
 
# ─────────────────────────────────────────────
# SIGNALS
# ─────────────────────────────────────────────
 
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={"role": "client"}
        )
 
 
@receiver(pre_delete, sender=User)
def protect_bot_user(sender, instance, **kwargs):
    if instance.username == "elicebot":
        raise PermissionDenied("The Elice bot user cannot be deleted.")