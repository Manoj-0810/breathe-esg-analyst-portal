from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date
from decimal import Decimal
from breathe_esg.models import Client, EmissionFactor

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds database with default superuser, clients, and DEFRA 2024 versioned emission factors."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Breathe ESG database...")

        # 1. Create Default User
        superuser_username = "admin"
        superuser_email = "admin@breatheesg.com"
        superuser_password = "adminpassword"

        if not User.objects.filter(username=superuser_username).exists():
            self.stdout.write(f"Creating default superuser '{superuser_username}'...")
            User.objects.create_superuser(
                username=superuser_username,
                email=superuser_email,
                password=superuser_password
            )
            self.stdout.write(self.style.SUCCESS("Superuser created successfully."))
        else:
            self.stdout.write(f"Superuser '{superuser_username}' already exists.")

        # 2. Create Default Client
        client_name = "ACME UK Corp"
        client, created = Client.objects.get_or_create(name=client_name)
        if created:
            self.stdout.write(self.style.SUCCESS(f"Client '{client_name}' created with ID: {client.id}"))
        else:
            self.stdout.write(f"Client '{client_name}' already exists with ID: {client.id}")

        # 3. Seed DEFRA 2024 Emission Factors
        factors_to_seed = [
            # Flights (Scope 3)
            {
                'source_type': EmissionFactor.SourceType.FLIGHT,
                'category': 'domestic',
                'sub_category': 'economy',
                'unit': 'kgCO2e_per_pkm',
                'factor_value': Decimal('0.255270000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- air',
                'valid_from': date(2024, 1, 1),
                'notes': 'Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology'
            },
            {
                'source_type': EmissionFactor.SourceType.FLIGHT,
                'category': 'short_haul',
                'sub_category': 'economy',
                'unit': 'kgCO2e_per_pkm',
                'factor_value': Decimal('0.153530000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- air',
                'valid_from': date(2024, 1, 1),
                'notes': 'Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology'
            },
            {
                'source_type': EmissionFactor.SourceType.FLIGHT,
                'category': 'short_haul',
                'sub_category': 'business',
                'unit': 'kgCO2e_per_pkm',
                'factor_value': Decimal('0.229430000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- air',
                'valid_from': date(2024, 1, 1),
                'notes': 'Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology'
            },
            {
                'source_type': EmissionFactor.SourceType.FLIGHT,
                'category': 'long_haul',
                'sub_category': 'economy',
                'unit': 'kgCO2e_per_pkm',
                'factor_value': Decimal('0.190850000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- air',
                'valid_from': date(2024, 1, 1),
                'notes': 'Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology'
            },
            {
                'source_type': EmissionFactor.SourceType.FLIGHT,
                'category': 'long_haul',
                'sub_category': 'premium_economy',
                'unit': 'kgCO2e_per_pkm',
                'factor_value': Decimal('0.286270000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- air',
                'valid_from': date(2024, 1, 1),
                'notes': 'Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology'
            },
            {
                'source_type': EmissionFactor.SourceType.FLIGHT,
                'category': 'long_haul',
                'sub_category': 'business',
                'unit': 'kgCO2e_per_pkm',
                'factor_value': Decimal('0.428720000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- air',
                'valid_from': date(2024, 1, 1),
                'notes': 'Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology'
            },
            {
                'source_type': EmissionFactor.SourceType.FLIGHT,
                'category': 'long_haul',
                'sub_category': 'first',
                'unit': 'kgCO2e_per_pkm',
                'factor_value': Decimal('0.763440000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- air',
                'valid_from': date(2024, 1, 1),
                'notes': 'Includes Radiative Forcing Index (RFI) multiplier per DEFRA methodology'
            },
            # Hotels (Scope 3)
            {
                'source_type': EmissionFactor.SourceType.HOTEL,
                'category': 'uk',
                'sub_category': '',
                'unit': 'kgCO2e_per_room_night',
                'factor_value': Decimal('11.600000000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Hotel stay',
                'valid_from': date(2024, 1, 1),
                'notes': 'Cornell CHSB index methodology'
            },
            {
                'source_type': EmissionFactor.SourceType.HOTEL,
                'category': 'world',
                'sub_category': '',
                'unit': 'kgCO2e_per_room_night',
                'factor_value': Decimal('33.400000000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Hotel stay',
                'valid_from': date(2024, 1, 1),
                'notes': 'Cornell CHSB index methodology'
            },
            # Ground Transport (Scope 3)
            {
                'source_type': EmissionFactor.SourceType.GROUND,
                'category': 'taxi',
                'sub_category': '',
                'unit': 'kgCO2e_per_km',
                'factor_value': Decimal('0.148860000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- land',
                'valid_from': date(2024, 1, 1),
                'notes': 'Average UK taxi travel'
            },
            {
                'source_type': EmissionFactor.SourceType.GROUND,
                'category': 'train',
                'sub_category': '',
                'unit': 'kgCO2e_per_km',
                'factor_value': Decimal('0.035490000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- land',
                'valid_from': date(2024, 1, 1),
                'notes': 'National Rail passenger travel average'
            },
            {
                'source_type': EmissionFactor.SourceType.GROUND,
                'category': 'bus',
                'sub_category': '',
                'unit': 'kgCO2e_per_km',
                'factor_value': Decimal('0.102750000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- land',
                'valid_from': date(2024, 1, 1),
                'notes': 'Average local bus passenger travel'
            },
            {
                'source_type': EmissionFactor.SourceType.GROUND,
                'category': 'car',
                'sub_category': '',
                'unit': 'kgCO2e_per_km',
                'factor_value': Decimal('0.168440000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Business travel- land',
                'valid_from': date(2024, 1, 1),
                'notes': 'Average petrol car'
            },
            # Fuel (Scope 1)
            {
                'source_type': EmissionFactor.SourceType.FUEL,
                'category': 'diesel',
                'sub_category': '',
                'unit': 'kgCO2e_per_litre',
                'factor_value': Decimal('2.516000000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Fuels',
                'valid_from': date(2024, 1, 1),
                'notes': 'Average commercial diesel (B7)'
            },
            {
                'source_type': EmissionFactor.SourceType.FUEL,
                'category': 'natural_gas',
                'sub_category': '',
                'unit': 'kgCO2e_per_kwh',
                'factor_value': Decimal('0.182900000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'Fuels',
                'valid_from': date(2024, 1, 1),
                'notes': 'Natural gas (gross CV)'
            },
            # Electricity (Scope 2)
            {
                'source_type': EmissionFactor.SourceType.ELECTRICITY,
                'category': 'uk',
                'sub_category': '',
                'unit': 'kgCO2e_per_kwh',
                'factor_value': Decimal('0.207060000'),
                'year': 2024,
                'source': 'DEFRA/DESNZ GHG Conversion Factors 2024',
                'source_url': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'source_sheet': 'UK electricity',
                'valid_from': date(2024, 1, 1),
                'notes': 'Grid electricity generation'
            }
        ]

        seeded_count = 0
        for f_data in factors_to_seed:
            obj, created = EmissionFactor.objects.get_or_create(
                source_type=f_data['source_type'],
                category=f_data['category'],
                sub_category=f_data['sub_category'],
                valid_from=f_data['valid_from'],
                defaults=f_data
            )
            if created:
                seeded_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {seeded_count} new DEFRA 2024 emission factors."))
        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully."))
