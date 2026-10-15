from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from store.models import PropaneTank, Store

# Demo shops placed on the streets around the map's default view.
# Each entry: name, latitude, longitude, description, {tank type: (price, stock)}
SHOPS = [
    (
        "Juan's LPG Center", 11.70653, 124.42188,
        "Fresh refills daily. Free delivery within the barangay.",
        {'A/S Valve Gasul': (950, 18), 'POL Valve Gasul': (920, 12), 'Price Gas': (880, 9)},
    ),
    (
        "Bayan Gas Station", 11.70514, 124.42314,
        "Beside the public market. Open 6 AM to 8 PM.",
        {'A/S Valve Gasul': (965, 10), 'Price Gas': (875, 20)},
    ),
    (
        "Maria's Sari-Sari & LPG", 11.70653, 124.42394,
        "Neighborhood store with Gasul and Price Gas refills.",
        {'POL Valve Gasul': (915, 8), 'Price Gas': (890, 6)},
    ),
    (
        "Biliran Petro Gas Supply", 11.70586, 124.42291,
        "Wholesale and retail LPG. Bulk orders welcome.",
        {'A/S Valve Gasul': (940, 30), 'POL Valve Gasul': (910, 25), 'Price Gas': (860, 40)},
    ),
    (
        "Kuya Ben's Gasul Depot", 11.70615, 124.42497,
        "Quick pickup, friendly service.",
        {'A/S Valve Gasul': (955, 5), 'POL Valve Gasul': (925, 0)},
    ),
]

DEMO_SELLER = 'demo_seller'


class Command(BaseCommand):
    help = "Add demo propane shops (safe to run more than once)."

    @transaction.atomic
    def handle(self, *args, **options):
        seller, created = User.objects.get_or_create(
            username=DEMO_SELLER,
            defaults={'first_name': 'Demo', 'last_name': 'Seller'},
        )
        if created:
            # Nobody can log in as the demo seller
            seller.set_unusable_password()
            seller.save()
        profile = seller.profile
        if profile.role != 'seller' or profile.status != 'approved':
            profile.role = 'seller'
            profile.status = 'approved'
            profile.save()

        added = 0
        for name, lat, lng, description, tanks in SHOPS:
            store, store_created = Store.objects.get_or_create(
                owner=seller,
                name=name,
                defaults={
                    'latitude': lat,
                    'longitude': lng,
                    'description': description,
                    # Empty photo: the map falls back to static/img/default.png
                    'owner_photo': '',
                },
            )
            if not store_created:
                continue
            added += 1
            for tank_type, (price, stock) in tanks.items():
                PropaneTank.objects.create(
                    store=store,
                    tank_type=tank_type,
                    price=Decimal(price),
                    stock=stock,
                )

        self.stdout.write(self.style.SUCCESS(
            f'Demo shops: {added} added, {len(SHOPS) - added} already existed.'
        ))
