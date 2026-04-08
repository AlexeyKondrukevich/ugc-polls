from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Generate test users with bulk_create (optimized)"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=1_000_000)
        parser.add_argument("--batch-size", type=int, default=10_000)
        parser.add_argument("--prefix", type=str, default="testuser")
        parser.add_argument("--password", type=str, default="testpass123")

    def handle(self, *args, **options):
        total_users = options["users"]
        batch_size = options["batch_size"]
        prefix = options["prefix"]
        raw_password = options["password"]

        # Хешируем пароль ОДИН РАЗ
        hashed_password = make_password(raw_password)

        self.stdout.write(f"Generating {total_users:,} users...")

        user_batch = []
        created_count = 0

        for i in range(1, total_users + 1):
            username = f"{prefix}_{i}"
            email = f"{username}@example.com"
            user = User(
                username=username, email=email, password=hashed_password
            )
            user_batch.append(user)

            if len(user_batch) >= batch_size or i == total_users:
                User.objects.bulk_create(user_batch)
                created_count += len(user_batch)
                self.stdout.write(f"Created {created_count:,} users...")
                user_batch = []

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {created_count:,} users with password '{raw_password}'"
            )
        )
