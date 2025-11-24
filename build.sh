#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Create admin user if it doesn't exist
python manage.py shell << END
from django.contrib.auth.models import User
from store.models import UserProfile

if not User.objects.filter(username='admin').exists():
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@propanepoint.com',
        password='juniel123'
    )
    profile = admin.profile
    profile.role = 'admin'
    profile.status = 'approved'
    profile.save()
    print('✅ Admin user created! Username: admin, Password: admin123')
else:
    admin = User.objects.get(username='admin')
    profile = admin.profile
    if profile.role != 'admin':
        profile.role = 'admin'
        profile.status = 'approved'
        profile.save()
        print('✅ Admin role updated!')
    else:
        print('✅ Admin user already exists')
END