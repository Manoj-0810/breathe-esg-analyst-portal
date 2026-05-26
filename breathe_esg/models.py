import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class IngestionJob(models.Model):
    class SourceType(models.TextChoices):
        SAP_MM = 'sap_mm', 'SAP MM (MB51)'
        UTILITY_HH = 'utility_hh', 'Utility HH Meter'
        TRAVEL_NAVAN = 'travel_navan', 'Navan Travel CSV'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETE = 'complete', 'Complete'
        FAILED = 'failed', 'Failed'
        PARTIAL = 'partial', 'Partial (with errors)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='ingestion_jobs')
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    original_filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ingestion_jobs')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    row_count_total = models.IntegerField(null=True, blank=True)
    row_count_success = models.IntegerField(null=True, blank=True)
    row_count_error = models.IntegerField(null=True, blank=True)
    error_detail = models.JSONField(null=True, blank=True)  # list of row error details
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.source_type} Job ({self.id}) - {self.status}"


class EmissionFactor(models.Model):
    class SourceType(models.TextChoices):
        FLIGHT = 'flight', 'Business Travel — Air'
        HOTEL = 'hotel', 'Hotel Stay'
        FUEL = 'fuel', 'Fuel Combustion'
        ELECTRICITY = 'electricity', 'Electricity (Grid)'
        GROUND = 'ground', 'Ground Transport'

    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    category = models.CharField(max_length=50)  # e.g., 'domestic', 'uk', 'diesel'
    sub_category = models.CharField(max_length=50, blank=True, default='')  # e.g., 'economy'
    unit = models.CharField(max_length=50)  # e.g., 'kgCO2e_per_pkm'
    factor_value = models.DecimalField(max_digits=18, decimal_places=9)
    year = models.IntegerField()
    source = models.CharField(max_length=200)
    source_url = models.URLField(blank=True)
    source_sheet = models.CharField(max_length=100, blank=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [('source_type', 'category', 'sub_category', 'valid_from')]
        indexes = [
            models.Index(fields=['source_type', 'category', 'sub_category', 'valid_from']),
        ]

    def __str__(self):
        sub = f'/{self.sub_category}' if self.sub_category else ''
        return f'{self.source_type}/{self.category}{sub} ({self.year}) = {self.factor_value} {self.unit}'


class EmissionRow(models.Model):
    class SourceType(models.TextChoices):
        SAP_MM = 'sap_mm', 'SAP MM (MB51)'
        UTILITY_HH = 'utility_hh', 'Utility HH Meter'
        TRAVEL_NAVAN = 'travel_navan', 'Navan Travel CSV'

    class Scope(models.TextChoices):
        SCOPE1 = '1', 'Scope 1 — Direct'
        SCOPE2 = '2', 'Scope 2 — Electricity'
        SCOPE3 = '3', 'Scope 3 — Value Chain'

    # --- Identity ---
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.PROTECT, related_name='emission_rows')
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_raw = models.JSONField()
    idempotency_key = models.CharField(max_length=100, unique=True)

    # --- Time ---
    activity_date = models.DateField()

    # --- Raw ---
    raw_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    raw_unit = models.CharField(max_length=20, null=True, blank=True)

    # --- Normalised ---
    scope = models.CharField(max_length=1, choices=Scope.choices, null=True, blank=True)
    emission_factor_used = models.ForeignKey(
        EmissionFactor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='emission_rows'
    )
    normalized_kgco2e = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    # --- Source-Specific Fields ---
    # SAP MM
    plant_code = models.CharField(max_length=4, null=True, blank=True)
    company_code = models.CharField(max_length=4, null=True, blank=True)
    material_code = models.CharField(max_length=40, null=True, blank=True)
    movement_type = models.CharField(max_length=3, null=True, blank=True)
    cost_centre = models.CharField(max_length=10, null=True, blank=True)

    # Utility HH
    mpan = models.CharField(max_length=13, null=True, blank=True)
    meter_serial = models.CharField(max_length=20, null=True, blank=True)
    has_estimated_periods = models.BooleanField(null=True, blank=True)

    # Navan Travel
    travel_category = models.CharField(max_length=20, null=True, blank=True)
    origin_iata = models.CharField(max_length=3, null=True, blank=True)
    destination_iata = models.CharField(max_length=3, null=True, blank=True)
    cabin_class = models.CharField(max_length=20, null=True, blank=True)
    carrier_code = models.CharField(max_length=2, null=True, blank=True)
    hotel_country = models.CharField(max_length=2, null=True, blank=True)
    nights = models.IntegerField(null=True, blank=True)
    inferred_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_id = models.CharField(max_length=30, null=True, blank=True)
    employee_id = models.CharField(max_length=20, null=True, blank=True)

    # --- Data Quality ---
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=255, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_rows'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['source_type', 'activity_date']),
            models.Index(fields=['ingestion_job']),
            models.Index(fields=['mpan', 'activity_date']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self):
        return f"{self.source_type} Row ({self.id}) - {self.activity_date}"


class AuditLog(models.Model):
    class Action(models.TextChoices):
        APPROVE = 'approve', 'Approved'
        FLAG = 'flag', 'Flagged for Review'
        EDIT = 'edit', 'Value Edited'
        REVERT = 'revert', 'Edit Reverted'
        UPLOAD = 'upload', 'File Uploaded'
        REPROCESS = 'reprocess', 'Job Reprocessed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=Action.choices)

    # Target (polymorphic relation to what is modified)
    emission_row = models.ForeignKey(
        EmissionRow,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    ingestion_job = models.ForeignKey(
        IngestionJob,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='audit_logs'
    )

    # Payload
    before_value = models.JSONField(null=True, blank=True)
    after_value = models.JSONField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def save(self, *args, **kwargs):
        # Enforce append-only in Python / Django ORM level
        if not self._state.adding:
            raise ValidationError("AuditLog is append-only. Modifying records is not permitted.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Enforce append-only by blocking deletes
        raise ValidationError("AuditLog is append-only. Deleting records is not permitted.")

    def __str__(self):
        return f"AuditLog {self.action} at {self.timestamp} by {self.user}"
