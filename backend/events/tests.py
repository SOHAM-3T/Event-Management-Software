from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Attendance, AttendanceStatus, Event, Participant, ParticipantSource


class GoogleSheetSyncTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            name='Demo Event',
            date='2026-10-12',
            venue='Auditorium',
        )

    def test_sync_creates_participant_with_absent_attendance_and_skips_duplicates(self):
        from .services import sync_google_sheet_rows

        rows = [{
            'Response ID': 'resp-001',
            'Timestamp': '2026-10-01 09:00:00',
            'Name': 'Riya Sharma',
            'Roll Number': '21CS101',
            'Email': 'riya@example.com',
            'Phone Number': '9876543210',
            'Branch': 'CSE',
        }]

        result = sync_google_sheet_rows(self.event, rows, {
            'response_id': 'Response ID',
            'name': 'Name',
            'roll_number': 'Roll Number',
            'email': 'Email',
            'phone': 'Phone Number',
            'branch': 'Branch',
            'registration_timestamp': 'Timestamp',
        })

        self.assertEqual(result['new_records'], 1)
        self.assertEqual(result['duplicate_records'], 0)
        participant = self.event.participants.get(name='Riya Sharma')
        self.assertEqual(participant.email, 'riya@example.com')
        self.assertEqual(participant.attendance.status, AttendanceStatus.ABSENT)

        second = sync_google_sheet_rows(self.event, rows, {
            'response_id': 'Response ID',
            'name': 'Name',
            'roll_number': 'Roll Number',
            'email': 'Email',
            'phone': 'Phone Number',
            'branch': 'Branch',
            'registration_timestamp': 'Timestamp',
        })
        self.assertEqual(second['duplicate_records'], 1)
        self.assertEqual(self.event.participants.count(), 1)

    def test_sync_does_not_overwrite_existing_attendance_status(self):
        from .services import sync_google_sheet_rows

        participant = Participant.objects.create(
            event=self.event,
            name='Arjun Nair',
            roll_number='21CS118',
            email='arjun@example.com',
            branch='ECE',
            source=ParticipantSource.GOOGLE_SHEETS,
        )
        Attendance.objects.create(
            participant=participant,
            status=AttendanceStatus.PRESENT,
            checked_in_at=timezone.make_aware(datetime(2026, 10, 12, 9, 40), timezone.get_current_timezone()),
        )

        result = sync_google_sheet_rows(self.event, [{
            'Response ID': 'resp-002',
            'Timestamp': '2026-10-01 10:00:00',
            'Name': 'Arjun Nair',
            'Roll Number': '21CS118',
            'Email': 'arjun@example.com',
            'Phone Number': '9999999999',
            'Branch': 'ECE',
        }], {
            'response_id': 'Response ID',
            'name': 'Name',
            'roll_number': 'Roll Number',
            'email': 'Email',
            'phone': 'Phone Number',
            'branch': 'Branch',
            'registration_timestamp': 'Timestamp',
        })

        self.assertEqual(result['updated_records'], 1)
        participant.refresh_from_db()
        self.assertEqual(participant.attendance.status, AttendanceStatus.PRESENT)

    def test_sync_handles_missing_connection_object(self):
        from .services import sync_google_sheet_rows

        result = sync_google_sheet_rows(self.event, [{
            'Response ID': 'resp-003',
            'Timestamp': '2026-10-03 11:20:00',
            'Name': 'Sneha N.',
            'Roll Number': '21CS199',
            'Email': 'sneha@example.com',
            'Phone Number': '9876500000',
            'Branch': 'IT',
        }], {
            'response_id': 'Response ID',
            'name': 'Name',
            'roll_number': 'Roll Number',
            'email': 'Email',
            'phone': 'Phone Number',
            'branch': 'Branch',
            'registration_timestamp': 'Timestamp',
        })

        self.assertEqual(result['new_records'], 1)
        self.assertTrue(self.event.google_sheet_connection)

    def test_google_sheet_rows_are_converted_from_raw_values(self):
        from .services import convert_google_sheet_values_to_rows

        raw_values = [
            ['Response ID', 'Timestamp', 'Name', 'Roll Number', 'Email', 'Branch'],
            ['resp-100', '2026-10-03 08:00:00', 'Rohit Kumar', '21CS777', 'rohit@example.com', 'CSE'],
        ]

        rows = convert_google_sheet_values_to_rows(raw_values)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['Name'], 'Rohit Kumar')
        self.assertEqual(rows[0]['Roll Number'], '21CS777')

    def test_google_sheet_reference_parses_spreadsheet_url_and_gid(self):
        from .services import parse_google_sheet_reference

        spreadsheet_id, sheet_gid = parse_google_sheet_reference(
            'https://docs.google.com/spreadsheets/d/1hqKwlv8neM_Co3FPr0BsLgpfcrJytZZF1ZdQ-EUe6jA/edit?resourcekey=&gid=1614165359#gid=1614165359'
        )

        self.assertEqual(spreadsheet_id, '1hqKwlv8neM_Co3FPr0BsLgpfcrJytZZF1ZdQ-EUe6jA')
        self.assertEqual(sheet_gid, '1614165359')

    @patch('events.services.build_google_sheets_service')
    def test_sheet_fetch_resolves_gid_to_tab_title_before_reading_values(self, build_service):
        from .services import fetch_google_sheet_rows

        service = build_service.return_value
        service.spreadsheets.return_value.get.return_value.execute.return_value = {
            'sheets': [{'properties': {'sheetId': 1614165359, 'title': 'NIT Andhra Registrations'}}],
        }
        service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            'values': [['Name', 'Email'], ['Rohit Kumar', 'rohit@example.com']],
        }

        rows, resolved_sheet_name = fetch_google_sheet_rows(
            '1hqKwlv8neM_Co3FPr0BsLgpfcrJytZZF1ZdQ-EUe6jA', 'Sheet1', '1614165359'
        )

        self.assertEqual(resolved_sheet_name, 'NIT Andhra Registrations')
        self.assertEqual(rows[0]['Name'], 'Rohit Kumar')
        service.spreadsheets.return_value.values.return_value.get.assert_called_once_with(
            spreadsheetId='1hqKwlv8neM_Co3FPr0BsLgpfcrJytZZF1ZdQ-EUe6jA',
            range="'NIT Andhra Registrations'!A:ZZ",
        )

    @patch('events.views.fetch_google_sheet_rows')
    def test_live_sheet_sync_fetches_and_reuses_saved_connection(self, fetch_rows):
        fetch_rows.return_value = ([{
            'Timestamp': '2026-10-03 08:00:00',
            'Name': 'Rohit Kumar',
            'Roll Number': '21CS777',
            'Email': 'rohit@example.com',
            'Branch': 'CSE',
        }], 'Form Responses 1')
        user = get_user_model().objects.create_user(username='sheet-admin', password='test-password')
        client = APIClient()
        client.force_authenticate(user=user)
        endpoint = f'/api/events/{self.event.id}/sync/'

        response = client.post(endpoint, {
            'spreadsheet_id': 'sheet-id-123',
            'sheet_name': 'Form Responses 1',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['result']['new_records'], 1)
        self.assertEqual(self.event.google_sheet_connection.spreadsheet_id, 'sheet-id-123')
        self.assertEqual(self.event.google_sheet_connection.sheet_name, 'Form Responses 1')
        fetch_rows.assert_called_once_with('sheet-id-123', 'Form Responses 1', None)

        fetch_rows.reset_mock()
        second_response = client.post(endpoint, {}, format='json')

        self.assertEqual(second_response.status_code, 200)
        fetch_rows.assert_called_once_with('sheet-id-123', 'Form Responses 1', None)

    @patch('events.views.fetch_google_sheet_rows')
    def test_sync_accepts_full_google_sheet_url_and_uses_gid_tab_title(self, fetch_rows):
        fetch_rows.return_value = ([{
            'Name': 'Rohit Kumar',
            'Roll Number': '21CS777',
            'Email': 'rohit@example.com',
        }], 'NIT Andhra Registrations')
        user = get_user_model().objects.create_user(username='sheet-url-admin', password='test-password')
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(f'/api/events/{self.event.id}/sync/', {
            'spreadsheet_id': 'https://docs.google.com/spreadsheets/d/1hqKwlv8neM_Co3FPr0BsLgpfcrJytZZF1ZdQ-EUe6jA/edit?resourcekey=&gid=1614165359#gid=1614165359',
            'sheet_name': 'Sheet1',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['spreadsheet_id'], '1hqKwlv8neM_Co3FPr0BsLgpfcrJytZZF1ZdQ-EUe6jA')
        self.assertEqual(response.data['sheet_name'], 'NIT Andhra Registrations')
        fetch_rows.assert_called_once_with(
            '1hqKwlv8neM_Co3FPr0BsLgpfcrJytZZF1ZdQ-EUe6jA', 'Sheet1', '1614165359'
        )
