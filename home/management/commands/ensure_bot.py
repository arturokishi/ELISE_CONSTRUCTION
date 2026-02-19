# home/management/commands/ensure_bot.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from home.models import UserProfile

class Command(BaseCommand):
    help = 'Ensures the Elice bot user exists'

    def handle(self, *args, **options):
        bot_username = "elicebot"
        
        # Check if bot exists
        bot_user, created = User.objects.get_or_create(
            username=bot_username,
            defaults={
                'email': 'bot@elice.com',
                'first_name': 'Elice',
                'last_name': 'Bot',
                'is_staff': False,
                'is_superuser': False,
            }
        )
        
        if created:
            # Set a random unusable password (bot can't login)
            bot_user.set_unusable_password()
            bot_user.save()
            
            # Create or update profile
            profile, _ = UserProfile.objects.get_or_create(
                user=bot_user,
                defaults={
                    'role': 'client',
                    'company': 'Elice Construcción',
                }
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Bot user "{bot_username}" created successfully'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Bot user "{bot_username}" already exists'))