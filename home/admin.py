from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
 
from .models import (
    Order, OrderItem,
    UserProfile, Supplier,
    Conversation, Message,
    Category, Brand,
    Product, ProductImage, ProductSpecification,
    SpecificationTemplate, SpecificationField,
    QuoteRequest,
)
 
 
# ─────────────────────────────────────────────
# ORDERS
# ─────────────────────────────────────────────
 
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
 
 
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'user_email', 'phone', 'total', 'created_at')
    inlines = [OrderItemInline]
 
    def user_email(self, obj):
        return obj.user.email if obj.user else '-'
    user_email.short_description = "Email"
 
 
# ─────────────────────────────────────────────
# USERS & PROFILES
# ─────────────────────────────────────────────
 
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil de Usuario'
    extra = 0
 
    def has_add_permission(self, request, obj=None):
        if obj is not None:
            return not UserProfile.objects.filter(user=obj).exists()
        return False
 
 
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff')
 
    def get_role(self, obj):
        try:
            return obj.userprofile.get_role_display()
        except Exception:
            return 'No definido'
    get_role.short_description = 'Rol'
 
 
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
 
 
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'contact_name', 'country', 'city', 'is_active', 'is_verified')
    list_filter = ('is_active', 'is_verified', 'country')
    search_fields = ('user__username', 'contact_name', 'contact_email')
    filter_horizontal = ('categories', 'brands')
    fieldsets = (
        ('Usuario', {'fields': ('user',)}),
        ('Contacto', {'fields': ('contact_name', 'contact_email', 'contact_phone', 'website')}),
        ('Ubicación', {'fields': ('country', 'city', 'address')}),
        ('Negocio', {'fields': ('description', 'logo', 'categories', 'brands')}),
        ('Estado', {'fields': ('is_active', 'is_verified')}),
    )
 
 
# ─────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────
 
@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'participant_list', 'created_at', 'updated_at', 'is_active')
    filter_horizontal = ('participants',)
 
    def participant_list(self, obj):
        return ', '.join([user.username for user in obj.participants.all()])
    participant_list.short_description = 'Participantes'
 
 
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'conversation', 'content_preview', 'timestamp', 'is_read')
    list_filter = ('timestamp', 'is_read', 'sender')
    search_fields = ('content', 'sender__username')
 
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Mensaje'
 
 
# ─────────────────────────────────────────────
# CATEGORIES
# ─────────────────────────────────────────────
 
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'level_display', 'slug', 'order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('order', 'is_active')
 
    def level_display(self, obj):
        level = obj.level
        labels = {0: '🟦 Nivel 1 (Madre)', 1: '🟩 Nivel 2 (Familia)', 2: '🟨 Nivel 3 (Sub)'}
        return labels.get(level, f'Nivel {level + 1}')
    level_display.short_description = 'Nivel'
 
 
# ─────────────────────────────────────────────
# BRANDS
# ─────────────────────────────────────────────
 
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'website', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
 
 
# ─────────────────────────────────────────────
# SPECIFICATION TEMPLATES
# ─────────────────────────────────────────────
 
class SpecificationFieldInline(admin.TabularInline):
    model = SpecificationField
    extra = 1
    fields = ('name', 'key', 'field_type', 'unit', 'choices', 'is_required', 'is_filterable', 'order')
 
 
@admin.register(SpecificationTemplate)
class SpecificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_at')
    search_fields = ('name', 'category__name')
    inlines = [SpecificationFieldInline]
 
 
# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────
 
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'caption', 'order')
 
 
class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 0
    fields = ('field', 'value')
 
 
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'unit', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'brands', 'suppliers')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('suppliers', 'brands')
    inlines = [ProductImageInline, ProductSpecificationInline]
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'slug', 'category', 'description', 'base_price', 'unit')
        }),
        ('Proveedores y marcas', {
            'fields': ('suppliers', 'brands')
        }),
        ('Archivos', {
            'fields': ('main_image', 'technical_sheet')
        }),
        ('Control', {
            'fields': ('is_active',)
        }),
    )
 
 
# ─────────────────────────────────────────────
# QUOTES
# ─────────────────────────────────────────────
 
@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'supplier', 'product_name', 'status', 'created_at')
    list_filter = ('status', 'supplier')
    search_fields = ('client__username', 'product_name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Solicitud', {
            'fields': ('client', 'supplier', 'conversation', 'product_name', 'product_details', 'client_notes')
        }),
        ('Respuesta', {
            'fields': ('quoted_price', 'supplier_notes', 'valid_until', 'status')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
 