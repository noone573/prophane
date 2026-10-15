#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py setup_supabase
python manage.py seed_shops

# Create admin user if it doesn't exist.
# Set ADMIN_PASSWORD in Render's environment; it is never stored in the repo.
python manage.py shell << END
import os
from django.contrib.auth.models import User

password = os.environ.get('ADMIN_PASSWORD')
admin = User.objects.filter(username='admin').first()

if admin is None and not password:
    print('⚠️  ADMIN_PASSWORD is not set, skipping admin user creation')
else:
    if admin is None:
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@propanepoint.com',
            password=password,
        )
        print('✅ Admin user created (username: admin)')
    elif password and not admin.check_password(password):
        admin.set_password(password)
        admin.save()
        print('✅ Admin password updated from ADMIN_PASSWORD')
    else:
        print('✅ Admin user already exists')

    profile = admin.profile
    if profile.role != 'admin' or profile.status != 'approved':
        profile.role = 'admin'
        profile.status = 'approved'
        profile.save()
        print('✅ Admin role updated!')
END
