import uuid

from django.db import models


class EventStatus(models.TextChoices):
    UPCOMING = 'UPCOMING', 'Upcoming'
    LIVE = 'LIVE', 'Live'
    COMPLETED = 'COMPLETED', 'Completed'


class RegistrationSource(models.TextChoices):
    GOOGLE_FORMS = 'GOOGLE_FORMS', 'Google Forms'
    EXCEL = 'EXCEL', 'Excel'
    MANUAL = 'MANUAL', 'Manual'


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    venue = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.UPCOMING)
    registration_source = models.CharField(max_length=30, choices=RegistrationSource.choices, default=RegistrationSource.GOOGLE_FORMS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return self.name


class GoogleSheetConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField('Event', on_delete=models.CASCADE, related_name='google_sheet_connection')
    spreadsheet_id = models.CharField(max_length=255)
    sheet_name = models.CharField(max_length=255, default='Sheet1')
    column_mapping = models.JSONField(default=dict)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    sync_status = models.CharField(max_length=20, default='CONNECTED')
    last_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.event.name} - {self.spreadsheet_id}'


class ParticipantSource(models.TextChoices):
    GOOGLE_SHEETS = 'GOOGLE_SHEETS', 'Google Sheets'
    EXCEL = 'EXCEL', 'Excel'
    MANUAL = 'MANUAL', 'Manual'


class Participant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participants')
    name = models.CharField(max_length=255)
    roll_number = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    branch = models.CharField(max_length=255, blank=True, null=True)
    registration_timestamp = models.DateTimeField(blank=True, null=True)
    google_response_identifier = models.CharField(max_length=255, blank=True, null=True)
    raw_registration_data = models.JSONField(default=dict)
    source = models.CharField(max_length=30, choices=ParticipantSource.choices, default=ParticipantSource.GOOGLE_SHEETS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('event', 'google_response_identifier')

    def __str__(self):
        return f'{self.name} ({self.roll_number or "No roll"})'


class AttendanceStatus(models.TextChoices):
    ABSENT = 'ABSENT', 'Absent'
    PRESENT = 'PRESENT', 'Present'


class Attendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.OneToOneField(Participant, on_delete=models.CASCADE, related_name='attendance')
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.ABSENT)
    checked_in_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.participant.name} - {self.status}'


class SyncLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sync_logs')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default='SUCCESS')
    new_records = models.IntegerField(default=0)
    updated_records = models.IntegerField(default=0)
    duplicate_records = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.event.name} sync - {self.status}'
