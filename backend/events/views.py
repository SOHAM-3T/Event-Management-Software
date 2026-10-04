from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from googleapiclient.errors import HttpError
import json
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Attendance, AttendanceStatus, Event, GoogleSheetConnection, Participant
from .serializers import AttendanceSerializer, EventSerializer, ParticipantSerializer
from .services import fetch_google_sheet_rows, parse_google_sheet_reference, sync_google_sheet_rows


class EventListCreateView(generics.ListCreateAPIView):
    queryset = Event.objects.all().order_by('-created_at')
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]


class ParticipantListView(generics.ListAPIView):
    serializer_class = ParticipantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        event_id = self.kwargs.get('event_id')
        queryset = Participant.objects.filter(event_id=event_id).select_related('attendance').order_by('-created_at')
        attendance_filter = self.request.query_params.get('attendance')
        if attendance_filter:
            queryset = queryset.filter(attendance__status=attendance_filter.upper())
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(roll_number__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset


class AttendanceUpdateView(generics.UpdateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        participant_id = self.kwargs.get('participant_id')
        event_id = self.kwargs.get('event_id')
        participant = Participant.objects.get(id=participant_id, event_id=event_id)
        return participant.attendance

    def perform_update(self, serializer):
        attendance = serializer.instance
        new_status = serializer.validated_data.get('status')
        if new_status == AttendanceStatus.PRESENT and attendance.checked_in_at is None:
            attendance.checked_in_at = timezone.now()
        elif new_status == AttendanceStatus.ABSENT:
            attendance.checked_in_at = None
        serializer.save()


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sync_event_registrations(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    rows = request.data.get('rows') or []
    mapping = request.data.get('column_mapping') or None
    spreadsheet_id = request.data.get('spreadsheet_id') or request.data.get('sheet_id')
    sheet_gid = request.data.get('sheet_gid')
    sheet_name = request.data.get('sheet_name')

    if not spreadsheet_id and not rows:
        try:
            connection = event.google_sheet_connection
        except GoogleSheetConnection.DoesNotExist:
            connection = None
        if connection:
            spreadsheet_id = connection.spreadsheet_id
            sheet_name = sheet_name or connection.sheet_name

    sheet_name = sheet_name or 'Sheet1'

    if spreadsheet_id and not rows:
        spreadsheet_id, url_sheet_gid = parse_google_sheet_reference(spreadsheet_id)
        sheet_gid = sheet_gid or url_sheet_gid
        try:
            rows, sheet_name = fetch_google_sheet_rows(spreadsheet_id, sheet_name, sheet_gid)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except HttpError as exc:
            try:
                api_error = json.loads(exc.content.decode('utf-8')).get('error', {}).get('message')
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
                api_error = None
            detail = api_error or 'Check the spreadsheet ID, tab, API access, and sharing permissions.'
            return Response(
                {'detail': f'Google Sheets API request failed ({exc.resp.status}): {detail}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    if not isinstance(rows, list) or not rows:
        return Response(
            {'detail': 'No registration rows were found. Provide a spreadsheet ID, connect a sheet, or submit a non-empty JSON rows list.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = sync_google_sheet_rows(event, rows, mapping, spreadsheet_id=spreadsheet_id or None, sheet_name=sheet_name)
    return Response({
        'event_id': str(event.id),
        'spreadsheet_id': spreadsheet_id,
        'sheet_name': sheet_name,
        'result': result,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def event_dashboard(request, event_id):
    event = Event.objects.get(id=event_id)
    participants = Participant.objects.filter(event=event).select_related('attendance')
    total = participants.count()
    present = participants.filter(attendance__status='PRESENT').count()
    absent = participants.filter(attendance__status='ABSENT').count()
    attendance_percentage = round((present / total) * 100, 2) if total else 0

    return Response({
        'event': EventSerializer(event).data,
        'stats': {
            'total_registered': total,
            'present': present,
            'absent': absent,
            'attendance_percentage': attendance_percentage,
        },
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)
