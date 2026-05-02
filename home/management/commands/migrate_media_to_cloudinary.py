"""
Management command: migrate_media_to_cloudinary
================================================
Sube archivos locales de media/ a Cloudinary y actualiza la BD.

UBICACIÓN DE ESTE ARCHIVO:
    home/management/commands/migrate_media_to_cloudinary.py

USO:
    python manage.py migrate_media_to_cloudinary --dry-run   ← primero esto
    python manage.py migrate_media_to_cloudinary             ← cuando todo se vea bien
"""

import os
from pathlib import Path

import cloudinary
import cloudinary.uploader
from django.conf import settings
from django.core.management.base import BaseCommand


# ─────────────────────────────────────────────────────────────────────────────
# Campos a migrar: (app_label.ModelName, nombre_campo, resource_type)
#
#   resource_type:
#     "image" → imágenes (jpg, png, webp, etc.)
#     "raw"   → cualquier otro archivo (PDF, etc.)
# ─────────────────────────────────────────────────────────────────────────────
FIELDS_TO_MIGRATE = [
    ("home.Product",      "main_image",      "image"),  # products/images/
    ("home.Product",      "technical_sheet", "raw"),    # products/docs/ (PDFs)
    ("home.ProductImage", "image",           "image"),  # products/images/
    ("home.Category",     "image",           "image"),  # categories/
    ("home.Brand",        "logo",            "image"),  # brands/
    ("home.Supplier",     "logo",            "image"),  # suppliers/logos/
    ("home.UserProfile",  "catalog_pdf",     "raw"),    # catalogs/ (PDFs)
]

# Prefijos que indican que el valor YA está en Cloudinary (no es una ruta local)
CLOUDINARY_INDICATORS = ("http://", "https://", "cloudinary://")


def already_in_cloudinary(value: str, media_root: Path) -> bool:
    """
    Devuelve True si el valor ya apunta a Cloudinary o el campo está vacío.
    Lógica:
      1. Vacío/nulo → skip
      2. Empieza con http/https/cloudinary:// → ya es URL de Cloudinary → skip
      3. El archivo NO existe localmente → asumimos que ya fue migrado → skip
      4. El archivo SÍ existe localmente → hay que subirlo → no skip
    """
    if not value:
        return True
    if any(value.startswith(p) for p in CLOUDINARY_INDICATORS):
        return True
    local_path = media_root / value
    if not local_path.exists():
        return True  # no está local, asumimos migrado
    return False


def get_model(model_path: str):
    """Devuelve la clase del modelo dado 'app_label.ModelName'."""
    from django.apps import apps
    app_label, model_name = model_path.rsplit(".", 1)
    return apps.get_model(app_label, model_name)


class Command(BaseCommand):
    help = "Sube archivos locales de media/ a Cloudinary y actualiza la BD."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Muestra qué se haría sin realizar cambios reales.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        media_root = Path(settings.MEDIA_ROOT)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n╔══════════════════════════════════════╗"
                "\n║   MODO DRY-RUN — sin cambios reales  ║"
                "\n╚══════════════════════════════════════╝\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n╔══════════════════════════════════════╗"
                "\n║   MIGRACIÓN REAL — subiendo archivos  ║"
                "\n╚══════════════════════════════════════╝\n"
            ))

        stats = {"success": 0, "skipped": 0, "error": 0}

        for model_path, field_name, resource_type in FIELDS_TO_MIGRATE:

            self.stdout.write(self.style.HTTP_INFO(
                f"\n▶  {model_path}.{field_name}  "
                f"(tipo Cloudinary: {resource_type})"
            ))

            # ── Cargar modelo ────────────────────────────────────────────────
            try:
                Model = get_model(model_path)
            except LookupError as exc:
                self.stdout.write(self.style.ERROR(f"   ✗ Modelo no encontrado: {exc}"))
                stats["error"] += 1
                continue

            # ── Traer registros con valor en el campo ────────────────────────
            qs = Model.objects.exclude(
                **{f"{field_name}__isnull": True}
            ).exclude(
                **{f"{field_name}__exact": ""}
            )

            total = qs.count()
            if total == 0:
                self.stdout.write("   (sin registros con archivo)")
                continue

            self.stdout.write(f"   {total} registro(s) encontrado(s)")

            for obj in qs.iterator():
                field_value = str(getattr(obj, field_name))

                # ── SKIP: ya en Cloudinary o archivo no existe ───────────────
                if already_in_cloudinary(field_value, media_root):
                    self.stdout.write(
                        f"   [SKIP]  pk={obj.pk:<5}  {field_value}"
                    )
                    stats["skipped"] += 1
                    continue

                local_path = media_root / field_value

                # ── Calcular public_id para Cloudinary ───────────────────────
                # Imágenes: sin extensión  (Cloudinary la maneja solo)
                # Raw/PDF:  con extensión  (necesario para raw)
                relative = Path(field_value)
                if resource_type == "image":
                    public_id = str(relative.with_suffix("")).replace("\\", "/")
                else:
                    public_id = str(relative).replace("\\", "/")

                self.stdout.write(
                    f"   [{'DRY' if dry_run else 'SUBIR'}]  "
                    f"pk={obj.pk:<5}  {field_value}  →  {public_id}"
                )

                if dry_run:
                    stats["success"] += 1
                    continue

                # ── Subir a Cloudinary ───────────────────────────────────────
                try:
                    result = cloudinary.uploader.upload(
                        str(local_path),
                        public_id=public_id,
                        resource_type=resource_type,
                        overwrite=False,   # no sobreescribe si ya existe
                        invalidate=True,
                    )

                    # El valor que guardamos en BD es el public_id devuelto
                    new_value = result["public_id"]

                    # Para raw, Cloudinary devuelve el public_id CON extensión;
                    # django-cloudinary-storage lo espera así para FileField.
                    setattr(obj, field_name, new_value)
                    obj.save(update_fields=[field_name])

                    self.stdout.write(self.style.SUCCESS(
                        f"            ✓  guardado: {new_value}"
                    ))
                    stats["success"] += 1

                except cloudinary.exceptions.Error as exc:
                    self.stdout.write(self.style.ERROR(
                        f"            ✗  error Cloudinary pk={obj.pk}: {exc}"
                    ))
                    stats["error"] += 1

                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(self.style.ERROR(
                        f"            ✗  error inesperado pk={obj.pk}: {exc}"
                    ))
                    stats["error"] += 1

        # ── Resumen final ────────────────────────────────────────────────────
        self.stdout.write("\n" + "═" * 45)
        self.stdout.write(self.style.SUCCESS(f"  ✓  Subidos/procesados : {stats['success']}"))
        self.stdout.write(self.style.WARNING(f"  ⏭  Saltados           : {stats['skipped']}"))
        self.stdout.write(self.style.ERROR(  f"  ✗  Errores            : {stats['error']}"))
        self.stdout.write("═" * 45)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n→ Dry-run completado. Si todo se ve bien, corre:"
                "\n  python manage.py migrate_media_to_cloudinary\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n→ Migración completada.\n"
            ))
