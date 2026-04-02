from django.shortcuts import render, get_object_or_404
from home.models import Category, Product, Supplier, Brand
 
 
def home(request):
    featured_products = Product.objects.filter(
        is_active=True, featured=True
    ).prefetch_related('brands', 'suppliers')[:12]

    if not featured_products.exists():
        featured_products = Product.objects.filter(
            is_active=True
        ).prefetch_related('brands', 'suppliers').order_by('-created_at')[:12]

    suppliers = Supplier.objects.filter(
        is_active=True
    ).select_related('user__userprofile').order_by('-is_verified', 'user__username')[:12]

    brands = Brand.objects.filter(is_active=True).order_by('name')[:20]

    root_categories = Category.objects.filter(
        is_active=True, parent=None
    ).order_by('order', 'name')[:8]

    context = {
        'featured_products': featured_products,
        'suppliers': suppliers,
        'brands': brands,
        'root_categories': root_categories,
    }
    return render(request, 'home/landing.html', context)
 
 
def industrias(request):
    return render(request, "home/industrias.html")
 
 
def nosotros(request):
    return render(request, "home/nosotros.html")
 
 
def contacto(request):
    return render(request, "home/contacto.html")
 
 
# ─────────────────────────────────────────────
# PRODUCTOS — Vista principal (categorías raíz)
# ─────────────────────────────────────────────
 
def productos(request):
    """Muestra las categorías raíz (nivel 1, sin parent)."""
    root_categories = Category.objects.filter(
        parent=None,
        is_active=True
    ).order_by('order', 'name')
 
    return render(request, "home/productos.html", {
        "categories": root_categories,
    })
 
 
# ─────────────────────────────────────────────
# CATEGORÍA — Vista dinámica por slug
# ─────────────────────────────────────────────
 
def categoria(request, slug):
    """
    Vista genérica para cualquier categoría.
    - Si tiene hijos → muestra subcategorías como cartas
    - Si no tiene hijos → muestra productos de esa categoría
    """
    category = get_object_or_404(Category, slug=slug, is_active=True)
 
    children = category.children.filter(is_active=True).order_by('order', 'name')
 
    products = None
    if not children.exists():
        products = Product.objects.filter(
            category=category,
            is_active=True
        ).prefetch_related('suppliers__user__userprofile', 'brands')
 
    # Breadcrumb: lista de ancestros + categoría actual
    breadcrumb = category.ancestors + [category]
 
    return render(request, "home/categoria.html", {
        "category": category,
        "children": children,
        "products": products,
        "breadcrumb": breadcrumb,
    })
 
 
# ─────────────────────────────────────────────
# PRODUCTO — Detalle de producto individual
# ─────────────────────────────────────────────
 
def producto_detalle(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    specs = product.specifications.select_related('field').order_by('field__order')
    breadcrumb = []
    if product.category:
        breadcrumb = product.category.ancestors + [product.category]
 
    return render(request, "home/producto_detalle.html", {
        "product": product,
        "specs": specs,
        "breadcrumb": breadcrumb,
    })
 