from django.core.management.base import BaseCommand
from products.models import Dress


class Command(BaseCommand):
    help = 'Create 80 products with codes rg101-rg180 and varied prices'

    def handle(self, *args, **options):
        created = 0
        for index in range(1, 81):
            code = f'rg{100 + index}'
            price = 100000 + (index * 5000)
            obj, was_created = Dress.objects.get_or_create(
                code=code,
                defaults={'daily_rent_price': price},
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created {code} with price {price}'))
            else:
                self.stdout.write(self.style.WARNING(f'Already exists: {code}'))

        self.stdout.write(self.style.SUCCESS(f'Finished. Created {created} new products.'))
