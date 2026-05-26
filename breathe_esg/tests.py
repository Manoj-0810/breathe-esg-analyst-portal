import uuid
from decimal import Decimal
from datetime import date, datetime
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from breathe_esg.models import Client, IngestionJob, EmissionRow, EmissionFactor, AuditLog
from breathe_esg.parsers import (
    haversine_km,
    parse_german_decimal,
    find_latest_factor
)

User = get_user_model()


class ParsersLogicTestCase(TestCase):
    def setUp(self):
        # Seed basic emission factors for lookup
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.FUEL,
            category='diesel',
            sub_category='',
            unit='kgCO2e_per_litre',
            factor_value=Decimal('2.516000000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.FLIGHT,
            category='long_haul',
            sub_category='economy',
            unit='kgCO2e_per_pkm',
            factor_value=Decimal('0.190850000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )

    def test_haversine_distance(self):
        # LHR to JFK: coordinates are stored in FALLBACK_AIRPORTS
        # LHR (51.47002, -0.454295), JFK (40.639751, -73.778925)
        # Expected distance is ~5540 km. Let's verify it is close.
        dist = haversine_km('LHR', 'JFK')
        self.assertIsNotNone(dist)
        self.assertAlmostEqual(dist, 5539.0, delta=100.0)

        # Missing airport returns None
        dist_none = haversine_km('LHR', 'XYZ')
        self.assertNone = self.assertIsNone
        self.assertIsNone(dist_none)

    def test_german_decimal_parsing(self):
        # German notation with comma and periods
        self.assertEqual(parse_german_decimal("1.500,000"), Decimal('1500.000'))
        self.assertEqual(parse_german_decimal("2.250,50"), Decimal('2250.50'))
        self.assertEqual(parse_german_decimal(" 45,800 "), Decimal('45.800'))
        # Standard notation
        self.assertEqual(parse_german_decimal("1500.00"), Decimal('1500.00'))
        # Error handling
        with self.assertRaises(ValueError):
            parse_german_decimal("abc")

    def test_find_latest_factor(self):
        # Lookup on active factor date
        factor = find_latest_factor(
            source_type=EmissionFactor.SourceType.FUEL,
            category='diesel',
            date=date(2024, 3, 15)
        )
        self.assertIsNotNone(factor)
        self.assertEqual(factor.factor_value, Decimal('2.516000000'))

        # Date prior to valid_from should return None
        factor_past = find_latest_factor(
            source_type=EmissionFactor.SourceType.FUEL,
            category='diesel',
            date=date(2023, 12, 31)
        )
        self.assertIsNone(factor_past)


class AuditLogAppendOnlyTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_auditor', password='password')
        self.client_obj = Client.objects.create(name='ACME Test')
        self.job = IngestionJob.objects.create(
            client_id=self.client_obj,
            source_type=IngestionJob.SourceType.SAP_MM,
            original_filename='test.tsv',
            uploaded_by=self.user
        )

    def test_audit_log_immutable(self):
        # Creating a log is allowed
        log = AuditLog.objects.create(
            user=self.user,
            action=AuditLog.Action.UPLOAD,
            ingestion_job=self.job,
            note="Initial Ingest"
        )
        self.assertIsNotNone(log.id)

        # Modifying log throws ValidationError
        log.note = "Modified Ingest Note"
        with self.assertRaises(ValidationError):
            log.save()

        # Deleting log throws ValidationError
        with self.assertRaises(ValidationError):
            log.delete()


class BreatheEsgAPITestCase(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin_test',
            email='admin_test@breatheesg.com',
            password='adminpassword'
        )
        self.client_obj = Client.objects.create(name="ACME Corporate Test")
        
        # Seed DEFRA factors
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.FUEL,
            category='diesel',
            unit='kgCO2e_per_litre',
            factor_value=Decimal('2.516000000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.FUEL,
            category='natural_gas',
            unit='kgCO2e_per_kwh',
            factor_value=Decimal('0.182900000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.ELECTRICITY,
            category='uk',
            unit='kgCO2e_per_kwh',
            factor_value=Decimal('0.207060000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.FLIGHT,
            category='long_haul',
            sub_category='economy',
            unit='kgCO2e_per_pkm',
            factor_value=Decimal('0.190850000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.FLIGHT,
            category='domestic',
            sub_category='economy',
            unit='kgCO2e_per_pkm',
            factor_value=Decimal('0.255270000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.HOTEL,
            category='world',
            unit='kgCO2e_per_room_night',
            factor_value=Decimal('33.400000000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )
        EmissionFactor.objects.create(
            source_type=EmissionFactor.SourceType.GROUND,
            category='taxi',
            unit='kgCO2e_per_km',
            factor_value=Decimal('0.148860000'),
            year=2024,
            source='DEFRA 2024',
            valid_from=date(2024, 1, 1)
        )

    def test_sap_mm_ingestion_endpoint(self):
        url = reverse('api-ingest', kwargs={'source_type': 'sap_mm'})
        
        # Create standard SAP tsv data
        sap_data = (
            "Buchungskreis\tWerk\tMaterial\tMaterialkurztext\tBewegungsart\tBuchungsdatum\tMenge\tMeins\tKostenstelle\tLieferant\tMaterialbeleg\tJahr\n"
            "GB01\t1100\tDIESEL-B7\tDiesel B7 EN590\t101\t20240315\t1.500,000\tL\t4210\t0000100023\t5000012345\t2024\n"
            "GB01\t1100\tDIESEL-B7\tDiesel B7 EN590\t102\t20240320\t500,000\tL\t4210\t0000100023\t5000012346\t2024\n"
        )
        
        # Write into dummy file for upload
        import io
        file_obj = io.BytesIO(sap_data.encode('utf-8'))
        file_obj.name = 'MB51_March2024.txt'
        
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(url, {
            'file': file_obj,
            'client_id': str(self.client_obj.id)
        }, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'complete')
        self.assertEqual(response.data['row_count_total'], 2)
        self.assertEqual(response.data['row_count_success'], 2)
        
        # Verify database records
        rows = EmissionRow.objects.filter(source_type=EmissionRow.SourceType.SAP_MM)
        self.assertEqual(rows.count(), 2)
        
        # Check standard row values and reversal negated quantity
        row1 = rows.get(idempotency_key="sap_mm_5000012345_2024")
        self.assertEqual(row1.raw_value, Decimal('1500.0'))
        self.assertEqual(row1.normalized_kgco2e, Decimal('3774.0')) # 1500 * 2.516
        
        row2 = rows.get(idempotency_key="sap_mm_5000012346_2024")
        self.assertEqual(row2.raw_value, Decimal('-500.0'))
        self.assertEqual(row2.normalized_kgco2e, Decimal('-1258.0')) # -500 * 2.516

    def test_utility_hh_ingestion_endpoint(self):
        url = reverse('api-ingest', kwargs={'source_type': 'utility_hh'})
        
        hh_data = (
            "Stark Energy Data Export\n"
            "Account: ACME-UK-001\n"
            "Export Date: 15/04/2024\n"
            "Period: 01/03/2024 - 31/03/2024\n"
            "\n"
            "MPAN,Meter Serial,Date,00:00,00:00 Status,00:30,00:30 Status,01:00,01:00 Status,Total kWh,Reactive Total kVArh\n"
            "1012345678901,L14B02345,15/03/2024,2.400,A,2.100,A,1.500,E,6.00,0.0\n"
        )
        
        import io
        file_obj = io.BytesIO(hh_data.encode('utf-8'))
        file_obj.name = 'Utility_March2024.csv'
        
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(url, {
            'file': file_obj,
            'client_id': str(self.client_obj.id)
        }, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'complete')
        self.assertEqual(response.data['row_count_success'], 1)
        
        # Verify rows
        row = EmissionRow.objects.get(mpan="1012345678901")
        self.assertEqual(row.raw_value, Decimal('6.000000')) # 2.4 + 2.1 + 1.5
        self.assertEqual(row.has_estimated_periods, True) # E status for 01:00
        self.assertEqual(row.is_flagged, True) # should be flagged because has estimated periods
        self.assertIsNotNone(row.normalized_kgco2e)

    def test_navan_csv_ingestion_endpoint(self):
        url = reverse('api-ingest', kwargs={'source_type': 'travel_navan'})
        
        navan_data = (
            "Booking ID,Trip ID,Employee ID,Traveller Name,Travel Date,Booking Date,Category,Origin,Destination,Cabin Class,Carrier Code,Hotel Name,Hotel City,Hotel Country,Nights,Ground Type,Distance km,Amount,Currency,Policy Status,Department,Cost Centre\n"
            "NAV-2024-88421,TRP-001,EMP-042,Sarah Chen,15/03/2024,28/02/2024,flight,LHR,JFK,economy,BA,,,,,,,,842.50,GBP,approved,Engineering,4210\n"
            "NAV-2024-88422,TRP-001,EMP-042,Sarah Chen,18/03/2024,28/02/2024,hotel,,,,,Marriott Times Square,New York,US,3,,,320.00,USD,approved,Engineering,4210\n"
            "NAV-2024-88423,TRP-001,EMP-042,Sarah Chen,18/03/2024,18/03/2024,ground_transport,,,,,,,,,taxi,12.4,28.50,USD,approved,Engineering,4210\n"
            "NAV-2024-88424,TRP-001,EMP-042,Sarah Chen,19/03/2024,18/03/2024,ground_transport,,,,,,,,,taxi,,28.50,USD,approved,Engineering,4210\n" # Missing land distance
        )
        
        import io
        file_obj = io.BytesIO(navan_data.encode('utf-8'))
        file_obj.name = 'Travel_March2024.csv'
        
        self.client.force_authenticate(user=self.superuser)
        response = self.client.post(url, {
            'file': file_obj,
            'client_id': str(self.client_obj.id)
        }, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['row_count_total'], 4)
        
        # Check flight row
        flight_row = EmissionRow.objects.get(booking_id="NAV-2024-88421")
        self.assertAlmostEqual(float(flight_row.inferred_distance_km), 5539.0, delta=100.0)
        self.assertIsNotNone(flight_row.normalized_kgco2e)
        self.assertEqual(flight_row.is_flagged, False)
        
        # Check missing distance row is flagged and has NULL emissions
        missing_dist_row = EmissionRow.objects.get(booking_id="NAV-2024-88424")
        self.assertEqual(missing_dist_row.is_flagged, True)
        self.assertIsNone(missing_dist_row.normalized_kgco2e)
        self.assertEqual(missing_dist_row.flag_reason, "Missing distance_km for land travel.")

    def test_approve_and_flag_endpoints(self):
        # Create IngestionJob and flagged row
        job = IngestionJob.objects.create(
            client_id=self.client_obj,
            source_type=IngestionJob.SourceType.SAP_MM,
            original_filename='manual_test.txt',
            uploaded_by=self.superuser
        )
        row = EmissionRow.objects.create(
            ingestion_job=job,
            source_type=EmissionRow.SourceType.SAP_MM,
            source_raw={},
            idempotency_key="manual_row_1",
            activity_date=date(2024, 3, 1),
            raw_value=Decimal('100.0'),
            raw_unit='L',
            is_flagged=True,
            flag_reason="Test Flag"
        )
        
        # 1. Test Approve Endpoint
        approve_url = reverse('api-rows-approve', kwargs={'pk': str(row.id)})
        self.client.force_authenticate(user=self.superuser)
        
        response = self.client.post(approve_url, {'note': 'Verified invoice details.'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check DB State
        row.refresh_from_db()
        self.assertEqual(row.is_approved, True)
        self.assertEqual(row.is_flagged, False)
        self.assertEqual(row.approved_by, self.superuser)
        self.assertIsNotNone(row.approved_at)
        
        # Check Audit Log
        logs = AuditLog.objects.filter(emission_row=row)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action, AuditLog.Action.APPROVE)
        self.assertEqual(logs.first().note, 'Verified invoice details.')
        
        # 2. Test Flag Endpoint
        flag_url = reverse('api-rows-flag', kwargs={'pk': str(row.id)})
        response = self.client.post(flag_url, {
            'flag_reason': 'Re-checking quantity',
            'note': 'Need to confirm with vendor.'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        row.refresh_from_db()
        self.assertEqual(row.is_approved, False)
        self.assertEqual(row.is_flagged, True)
        self.assertEqual(row.flag_reason, 'Re-checking quantity')
        
        logs = AuditLog.objects.filter(emission_row=row)
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs.first().action, AuditLog.Action.FLAG)
        self.assertEqual(logs.first().note, 'Need to confirm with vendor.')

    def test_dashboard_aggregation_endpoint(self):
        job = IngestionJob.objects.create(
            client_id=self.client_obj,
            source_type=IngestionJob.SourceType.SAP_MM,
            original_filename='dashboard_test.txt',
            uploaded_by=self.superuser
        )
        # Create approved rows
        EmissionRow.objects.create(
            ingestion_job=job,
            source_type=EmissionRow.SourceType.SAP_MM,
            source_raw={},
            idempotency_key="dash_row_1",
            activity_date=date(2024, 3, 1),
            raw_value=Decimal('100.0'),
            raw_unit='L',
            scope=EmissionRow.Scope.SCOPE1,
            normalized_kgco2e=Decimal('251.60'),
            is_approved=True
        )
        EmissionRow.objects.create(
            ingestion_job=job,
            source_type=EmissionRow.SourceType.TRAVEL_NAVAN,
            source_raw={},
            idempotency_key="dash_row_2",
            activity_date=date(2024, 4, 15),
            raw_value=Decimal('10.0'),
            raw_unit='km',
            scope=EmissionRow.Scope.SCOPE3,
            normalized_kgco2e=Decimal('1.4886'),
            is_flagged=True # Not approved yet
        )

        dashboard_url = reverse('api-dashboard')
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify totals
        self.assertAlmostEqual(float(response.data['emissions_summary']['total_ingested_kgco2e']), 253.0886, places=4)
        self.assertAlmostEqual(float(response.data['emissions_summary']['total_approved_kgco2e']), 251.60, places=4)
        
        # Verify scope breakdown
        self.assertAlmostEqual(float(response.data['emissions_by_scope']['Scope 1']), 251.60, places=4)
        self.assertAlmostEqual(float(response.data['emissions_by_scope']['Scope 3']), 1.4886, places=4)
        
        # Verify data quality count
        self.assertEqual(response.data['data_quality']['total_rows'], 2)
        self.assertEqual(response.data['data_quality']['flagged_rows'], 1)
        self.assertEqual(response.data['data_quality']['approved_rows'], 1)
        self.assertEqual(response.data['data_quality']['pending_rows'], 0)
