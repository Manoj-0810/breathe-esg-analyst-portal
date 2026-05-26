from decimal import Decimal
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce, TruncMonth
from django.core.exceptions import ValidationError
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import get_user_model

from breathe_esg.models import Client, IngestionJob, EmissionRow, AuditLog, EmissionFactor
from breathe_esg.serializers import (
    IngestionJobSerializer,
    EmissionRowSerializer,
    AuditLogSerializer
)
from breathe_esg.parsers import (
    process_file_decoding,
    run_sap_mm_parser,
    run_utility_hh_parser,
    run_navan_csv_parser
)

User = get_user_model()


class IngestView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, source_type):
        if source_type not in ['sap_mm', 'utility_hh', 'travel_navan']:
            return Response(
                {"error": f"Invalid source type '{source_type}'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        file_obj = request.FILES.get('file')
        client_id = request.data.get('client_id')

        if not file_obj:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        if not client_id:
            client = Client.objects.first()
            if not client:
                client = Client.objects.create(name="ACME UK Corp")
        else:
            try:
                client = Client.objects.get(id=client_id)
            except (Client.DoesNotExist, ValidationError):
                client = Client.objects.first()
                if not client:
                    client = Client.objects.create(name="ACME UK Corp")

        # Retrieve or create system/uploading user
        user = request.user
        if not user or user.is_anonymous:
            # Fallback to superuser or system ingest user
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user, _ = User.objects.get_or_create(
                    username='system_ingest',
                    email='ingest@breatheesg.com'
                )

        # Batch-level Idempotency Check
        # If the file has the exact same name and size, and was already successfully completed,
        # return the existing job details to achieve idempotency on re-upload
        existing_job = IngestionJob.objects.filter(
            client_id=client,
            source_type=source_type,
            original_filename=file_obj.name,
            status=IngestionJob.Status.COMPLETE
        ).first()

        if existing_job:
            serializer = IngestionJobSerializer(existing_job)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Create new Job
        job = IngestionJob.objects.create(
            client_id=client,
            source_type=source_type,
            original_filename=file_obj.name,
            uploaded_by=user,
            status=IngestionJob.Status.PROCESSING
        )

        try:
            # Decode file lines
            file_lines = process_file_decoding(file_obj)

            # Route to appropriate parser
            if source_type == 'sap_mm':
                run_sap_mm_parser(job, file_lines)
            elif source_type == 'utility_hh':
                run_utility_hh_parser(job, file_lines)
            elif source_type == 'travel_navan':
                run_navan_csv_parser(job, file_lines)

            # Record file upload action in AuditLog
            AuditLog.objects.create(
                user=user,
                action=AuditLog.Action.UPLOAD,
                ingestion_job=job,
                note=f"Successfully uploaded and parsed file '{file_obj.name}'."
            )

            serializer = IngestionJobSerializer(job)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            job.status = IngestionJob.Status.FAILED
            job.error_detail = [{"error": str(e)}]
            job.completed_at = timezone.now()
            job.save()
            return Response(
                {"error": f"Failed to ingest file: {str(e)}", "job_id": job.id},
                status=status.HTTP_400_BAD_REQUEST
            )


class IngestionJobListView(APIView):
    def get(self, request):
        jobs = IngestionJob.objects.all().order_index = ['-uploaded_at']
        # Wait, let's just order by uploaded_at descending
        jobs = IngestionJob.objects.all().order_by('-uploaded_at')
        serializer = IngestionJobSerializer(jobs, many=True)
        return Response(serializer.data)


class IngestionJobRowsView(APIView):
    def get(self, request, pk):
        try:
            job = IngestionJob.objects.get(id=pk)
        except (IngestionJob.DoesNotExist, ValidationError):
            return Response({"error": "Ingestion job not found"}, status=status.HTTP_404_NOT_FOUND)

        rows = EmissionRow.objects.filter(ingestion_job=job).order_by('activity_date')
        serializer = EmissionRowSerializer(rows, many=True)
        return Response(serializer.data)


class ApproveRowView(APIView):
    def post(self, request, pk):
        try:
            row = EmissionRow.objects.get(id=pk)
        except (EmissionRow.DoesNotExist, ValidationError):
            return Response({"error": "Emission row not found"}, status=status.HTTP_404_NOT_FOUND)

        note = request.data.get('note', '')

        # Capture snapshot before modification for AuditLog
        before_value = {
            "is_approved": row.is_approved,
            "is_flagged": row.is_flagged,
            "approved_by_id": str(row.approved_by.id) if row.approved_by else None,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None
        }

        user = request.user
        if not user or user.is_anonymous:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user, _ = User.objects.get_or_create(
                    username='system_audit',
                    email='audit@breatheesg.com'
                )

        row.is_approved = True
        row.is_flagged = False
        row.approved_by = user
        row.approved_at = timezone.now()
        row.save()

        after_value = {
            "is_approved": row.is_approved,
            "is_flagged": row.is_flagged,
            "approved_by_id": str(row.approved_by.id),
            "approved_at": row.approved_at.isoformat()
        }

        # Create immutable AuditLog
        AuditLog.objects.create(
            user=user,
            action=AuditLog.Action.APPROVE,
            emission_row=row,
            before_value=before_value,
            after_value=after_value,
            note=note
        )

        serializer = EmissionRowSerializer(row)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FlagRowView(APIView):
    def post(self, request, pk):
        try:
            row = EmissionRow.objects.get(id=pk)
        except (EmissionRow.DoesNotExist, ValidationError):
            return Response({"error": "Emission row not found"}, status=status.HTTP_404_NOT_FOUND)

        flag_reason = request.data.get('flag_reason')
        if not flag_reason:
            return Response({"error": "Missing flag_reason"}, status=status.HTTP_400_BAD_REQUEST)

        note = request.data.get('note', '')

        # Capture snapshot before modification for AuditLog
        before_value = {
            "is_approved": row.is_approved,
            "is_flagged": row.is_flagged,
            "flag_reason": row.flag_reason
        }

        user = request.user
        if not user or user.is_anonymous:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user, _ = User.objects.get_or_create(
                    username='system_audit',
                    email='audit@breatheesg.com'
                )

        row.is_approved = False
        row.is_flagged = True
        row.flag_reason = flag_reason
        row.save()

        after_value = {
            "is_approved": row.is_approved,
            "is_flagged": row.is_flagged,
            "flag_reason": row.flag_reason
        }

        # Create immutable AuditLog
        AuditLog.objects.create(
            user=user,
            action=AuditLog.Action.FLAG,
            emission_row=row,
            before_value=before_value,
            after_value=after_value,
            note=note
        )

        serializer = EmissionRowSerializer(row)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DashboardView(APIView):
    def get(self, request):
        # We aggregate carbon calculations across all records
        all_rows = EmissionRow.objects.all()

        # 1. Total Emissions Calculations
        total_emissions = all_rows.aggregate(
            total=Coalesce(Sum('normalized_kgco2e'), Decimal('0.000000'))
        )['total']
        
        approved_emissions = all_rows.filter(is_approved=True).aggregate(
            total=Coalesce(Sum('normalized_kgco2e'), Decimal('0.000000'))
        )['total']

        # 2. Scope-based Aggregations
        emissions_by_scope = all_rows.values('scope').annotate(
            total=Coalesce(Sum('normalized_kgco2e'), Decimal('0.000000'))
        )
        scope_data = {
            "Scope 1": Decimal('0.000000'),
            "Scope 2": Decimal('0.000000'),
            "Scope 3": Decimal('0.000000')
        }
        for item in emissions_by_scope:
            scope_val = item['scope']
            if scope_val == '1':
                scope_data["Scope 1"] = item['total']
            elif scope_val == '2':
                scope_data["Scope 2"] = item['total']
            elif scope_val == '3':
                scope_data["Scope 3"] = item['total']

        # 3. Source-based Aggregations
        emissions_by_source = all_rows.values('source_type').annotate(
            total=Coalesce(Sum('normalized_kgco2e'), Decimal('0.000000'))
        )
        source_data = {}
        for item in emissions_by_source:
            source_data[item['source_type']] = item['total']

        # 4. Data Quality Metrics
        quality_metrics = all_rows.aggregate(
            total_count=Count('id'),
            flagged_count=Count('id', filter=Q(is_flagged=True)),
            approved_count=Count('id', filter=Q(is_approved=True)),
        )
        total_count = quality_metrics['total_count']
        flagged_count = quality_metrics['flagged_count']
        approved_count = quality_metrics['approved_count']
        pending_count = total_count - flagged_count - approved_count

        # 5. Monthly Trend
        monthly_trend_qs = all_rows.annotate(
            month=TruncMonth('activity_date')
        ).values('month').annotate(
            total=Coalesce(Sum('normalized_kgco2e'), Decimal('0.000000'))
        ).order_by('month')

        monthly_trend = []
        for item in monthly_trend_qs:
            if item['month']:
                monthly_trend.append({
                    "month": item['month'].strftime('%Y-%m'),
                    "emissions_kgco2e": item['total']
                })

        return Response({
            "emissions_summary": {
                "total_ingested_kgco2e": total_emissions,
                "total_approved_kgco2e": approved_emissions
            },
            "emissions_by_scope": scope_data,
            "emissions_by_source": source_data,
            "data_quality": {
                "total_rows": total_count,
                "flagged_rows": flagged_count,
                "approved_rows": approved_count,
                "pending_rows": pending_count,
                "completeness_score_pct": (approved_count / total_count * 100) if total_count > 0 else 100.0
            },
            "monthly_trend": monthly_trend
        })


class AuditLogListView(APIView):
    def get(self, request):
        logs = AuditLog.objects.all().order_by('-timestamp')
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)

