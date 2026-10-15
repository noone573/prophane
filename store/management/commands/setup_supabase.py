from django.conf import settings
from django.core.management.base import BaseCommand

from store.storage import SupabaseStorage


class Command(BaseCommand):
    help = "Create the private Supabase Storage bucket for uploads if it doesn't exist."

    def handle(self, *args, **options):
        if not settings.USE_SUPABASE_STORAGE:
            self.stdout.write('SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set; uploads stay on local disk.')
            return
        created = SupabaseStorage().ensure_bucket()
        bucket = settings.SUPABASE_BUCKET
        self.stdout.write(self.style.SUCCESS(
            f'Created Supabase bucket "{bucket}".' if created else f'Supabase bucket "{bucket}" is ready.'
        ))
