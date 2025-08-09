from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Create a superuser if none exists'

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
        first_name = os.environ.get('DJANGO_SUPERUSER_FIRST_NAME', 'Admin')
        last_name = os.environ.get('DJANGO_SUPERUSER_LAST_NAME', 'User')
        if not User.objects.filter(email=email).exists():
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            # Ensure superuser is active and verified
            user.is_active = True
            user.is_verified = True
            user.save()
            self.stdout.write(self.style.SUCCESS('Superuser created and activated.'))
        else:
            # Optionally, update existing superuser to be active/verified
            user = User.objects.get(email=email)
            updated = False
            if not user.is_active:
                user.is_active = True
                updated = True
            if not user.is_verified:
                user.is_verified = True
                updated = True
            if updated:
                user.save()
                self.stdout.write(self.style.SUCCESS('Superuser updated to active and verified.'))
            else:
                self.stdout.write(self.style.WARNING('Superuser already exists and is active/verified.'))