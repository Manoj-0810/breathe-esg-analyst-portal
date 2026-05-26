from rest_framework import serializers
from django.contrib.auth import get_user_model
from breathe_esg.models import Client, IngestionJob, EmissionRow, AuditLog, EmissionFactor

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'name']


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = '__all__'


class IngestionJobSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    class Meta:
        model = IngestionJob
        fields = [
            'id', 'client_id', 'source_type', 'original_filename',
            'uploaded_by', 'uploaded_at', 'status', 'row_count_total',
            'row_count_success', 'row_count_error', 'error_detail', 'completed_at'
        ]


class EmissionRowSerializer(serializers.ModelSerializer):
    emission_factor_used = EmissionFactorSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

    class Meta:
        model = EmissionRow
        fields = '__all__'


class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'
