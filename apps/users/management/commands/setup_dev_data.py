from django.core.management.base import BaseCommand
from apps.users.models import CustomUser

class Command(BaseCommand):
    help = 'Sets up initial development data including test accounts'

    def handle(self, *args, **kwargs):
        test_users = [
            {'email': 'alice@example.com', 'username': 'alice'},
            {'email': 'bob@example.com', 'username': 'bob'},
            {'email': 'charlie@example.com', 'username': 'charlie'},
        ]

        for user_data in test_users:
            user, created = CustomUser.objects.get_or_create(
                email=user_data['email'],
                defaults={'username': user_data['username']}
            )
            if created:
                user.set_password('pass@123')
                user.is_verified = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created test user: {user.email} with password: pass@123"))
            else:
                self.stdout.write(self.style.WARNING(f"Test user already exists: {user.email}"))

        self.stdout.write(self.style.SUCCESS('Successfully set up development data.'))
