from django.contrib import admin
from .models import Order, OrderItem
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Conversation, Message
from .models import ProductCategory, Product, ProductOption, QuoteRequest


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0



@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "user_email",
        "phone",
        "total",
        "created_at",
    )
    inlines = [OrderItemInline]

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Email"



# Inline admin for UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil de Usuario'

# Extend User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff')
    
    def get_role(self, obj):
        try:
            return obj.userprofile.get_role_display()
        except:
            return 'No definido'
    get_role.short_description = 'Rol'

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'participant_list', 'created_at', 'updated_at', 'is_active')
    filter_horizontal = ('participants',)
    
    def participant_list(self, obj):
        return ', '.join([user.username for user in obj.participants.all()])

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'conversation', 'content_preview', 'timestamp', 'is_read')
    list_filter = ('timestamp', 'is_read', 'sender')
    search_fields = ('content', 'sender__username')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    

def open_chat(self, obj):
    if obj.conversation:
        return format_html(
            '<a href="/chat/{}/">Abrir chat</a>',
            obj.conversation.id
        )
    return "-"






class ProductOptionInline(admin.TabularInline):
    model = ProductOption
    extra = 1

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'icon']
    list_editable = ['order']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'supplier', 'category', 'base_price', 'is_active']
    list_filter = ['supplier', 'category', 'is_active']
    search_fields = ['name', 'description']
    inlines = [ProductOptionInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(supplier=request.user)
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # New product
            obj.supplier = request.user
        super().save_model(request, obj, form, change)

@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'supplier', 'product_name', 'status', 'created_at']
    list_filter = ['status', 'supplier']
    search_fields = ['client__username', 'product_name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Request', {
            'fields': ('client', 'supplier', 'conversation', 'product_name', 'product_details', 'client_notes')
        }),
        ('Response', {
            'fields': ('quoted_price', 'supplier_notes', 'valid_until', 'status')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )