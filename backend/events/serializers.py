from rest_framework import serializers

from .models import Attendance, Event, Participant


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'id',
            'name',
            'description',
            'date',
            'start_time',
            'end_time',
            'venue',
            'status',
            'registration_source',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ParticipantSerializer(serializers.ModelSerializer):
    attendance_status = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = [
            'id',
            'event',
            'name',
            'roll_number',
            'email',
            'phone',
            'branch',
            'registration_timestamp',
            'source',
            'google_response_identifier',
            'attendance_status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_attendance_status(self, obj):
        attendance = getattr(obj, 'attendance', None)
        return attendance.status if attendance else 'ABSENT'


class AttendanceSerializer(serializers.ModelSerializer):
    participant_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'id',
            'participant',
            'participant_name',
            'status',
            'checked_in_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def get_participant_name(self, obj):
        return obj.participant.name
