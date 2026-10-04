import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from django.utils import timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build

from .models import Attendance, AttendanceStatus, Event, GoogleSheetConnection, Participant, ParticipantSource, SyncLog


COLUMN_ALIASES = {
    'name': ['name', 'full name', 'student name', 'participant name'],
    'roll_number': ['roll no', 'roll number', 'registration number', 'student id', 'roll'],
    'email': ['email', 'email id', 'email address', 'e-mail'],
    'phone': ['phone', 'phone number', 'mobile', 'mobile number', 'contact number'],
    'branch': ['branch', 'department', 'course', 'program'],
    'registration_timestamp': ['timestamp', 'registration time', 'registered at', 'submitted at'],
    'response_id': ['response id', 'google form response id', 'responseid', 'form response id'],
}


def normalize_header(value):
    if value is None:
        return ''
    return re.sub(r'[^a-z0-9]+', ' ', str(value).strip().lower()).strip()


def detect_column_mapping(headers):
    normalized_headers = [normalize_header(header) for header in headers]
    mapping = {}
    for field, aliases in COLUMN_ALIASES.items():
        for index, header in enumerate(normalized_headers):
            if header in aliases or header in {alias.replace(' ', '') for alias in aliases}:
                mapping[field] = headers[index]
                break
    return mapping


def normalize_value(value):
    if value is None:
        return ''
    return str(value).strip()


def convert_google_sheet_values_to_rows(raw_values):
    if not raw_values or len(raw_values) < 2:
        return []

    headers = [str(value).strip() for value in raw_values[0]]
    rows = []
    for row in raw_values[1:]:
        item = {}
        for index, header in enumerate(headers):
            item[header] = row[index] if index < len(row) else ''
        rows.append(item)
    return rows


def parse_google_sheet_reference(reference):
    reference = (reference or '').strip()
    if not reference:
        return '', None

    parsed_url = urlparse(reference)
    match = re.search(r'/spreadsheets/d/([^/]+)', parsed_url.path)
    if not match:
        return reference, None

    query_values = parse_qs(parsed_url.query)
    fragment_values = parse_qs(parsed_url.fragment)
    sheet_gid = (query_values.get('gid') or fragment_values.get('gid') or [None])[0]
    return match.group(1), sheet_gid


def build_google_sheets_service():
    credentials_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', '').strip()
    credentials_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '').strip()
    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    if credentials_file:
        credential_path = Path(credentials_file)
        if not credential_path.is_absolute():
            credential_path = Path(__file__).resolve().parents[1] / credential_path
        if not credential_path.is_file():
            raise ValueError(f'Google service account key file was not found: {credential_path}')
        credentials = service_account.Credentials.from_service_account_file(
            str(credential_path), scopes=scopes
        )
    elif credentials_json:
        try:
            service_account_info = json.loads(credentials_json)
        except json.JSONDecodeError as exc:
            raise ValueError('GOOGLE_SERVICE_ACCOUNT_JSON must be valid JSON.') from exc
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=scopes
        )
    else:
        raise ValueError(
            'Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON in the backend .env file.'
        )

    return build('sheets', 'v4', credentials=credentials)


def fetch_google_sheet_rows(spreadsheet_id, sheet_name='Sheet1', sheet_gid=None):
    spreadsheet_id, url_sheet_gid = parse_google_sheet_reference(spreadsheet_id)
    sheet_gid = str(sheet_gid or url_sheet_gid or '').strip() or None
    sheet_name = (sheet_name or 'Sheet1').strip() or 'Sheet1'

    if not spreadsheet_id:
        raise ValueError('A spreadsheet ID is required to read Google Sheets data.')

    service = build_google_sheets_service()
    if sheet_gid:
        try:
            sheet_id = int(sheet_gid)
        except ValueError as exc:
            raise ValueError('The Google Sheets tab gid must be a number.') from exc
        metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='sheets(properties(sheetId,title))',
        ).execute()
        matching_sheet = next(
            (
                sheet.get('properties', {})
                for sheet in metadata.get('sheets', [])
                if sheet.get('properties', {}).get('sheetId') == sheet_id
            ),
            None,
        )
        if not matching_sheet:
            raise ValueError(f'No worksheet with gid {sheet_gid} exists in this spreadsheet.')
        sheet_name = matching_sheet['title']

    quoted_sheet_name = sheet_name.replace("'", "''")
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{quoted_sheet_name}'!A:ZZ",
    ).execute()

    return convert_google_sheet_values_to_rows(response.get('values', [])), sheet_name


def parse_registration_timestamp(raw_value):
    if not raw_value:
        return None
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%m/%d/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
    ]
    for fmt in formats:
        try:
            return timezone.make_aware(datetime.strptime(str(raw_value), fmt), timezone.get_current_timezone())
        except ValueError:
            continue
    try:
        return timezone.make_aware(datetime.fromisoformat(str(raw_value)), timezone.get_current_timezone())
    except ValueError:
        return None


def build_participant_identity(row, mapping):
    response_id = normalize_value(row.get(mapping.get('response_id')) if mapping.get('response_id') else '')
    roll_number = normalize_value(row.get(mapping.get('roll_number')) if mapping.get('roll_number') else '')
    email = normalize_value(row.get(mapping.get('email')) if mapping.get('email') else '')
    name = normalize_value(row.get(mapping.get('name')) if mapping.get('name') else '')
    return response_id or roll_number or email or name


def sync_google_sheet_rows(event, rows, column_mapping=None, spreadsheet_id=None, sheet_name='Sheet1'):
    if not rows:
        return {'new_records': 0, 'updated_records': 0, 'duplicate_records': 0}

    mapping = column_mapping or detect_column_mapping(list(rows[0].keys()))
    sync_log = SyncLog.objects.create(event=event, status='SUCCESS')
    result = {'new_records': 0, 'updated_records': 0, 'duplicate_records': 0}

    try:
        connection = event.google_sheet_connection
    except GoogleSheetConnection.DoesNotExist:
        connection = None

    if connection is None:
        connection = GoogleSheetConnection.objects.create(
            event=event,
            spreadsheet_id=spreadsheet_id or 'UNKNOWN',
            sheet_name=sheet_name,
            column_mapping=mapping,
            sync_status='CONNECTED',
        )
    else:
        if spreadsheet_id:
            connection.spreadsheet_id = spreadsheet_id
        connection.sheet_name = sheet_name
        connection.column_mapping = mapping
        connection.sync_status = 'SYNCED'
        connection.last_error = ''
        connection.save(update_fields=['spreadsheet_id', 'sheet_name', 'column_mapping', 'sync_status', 'last_error', 'updated_at'])

    try:
        for row in rows:
            response_id = normalize_value(row.get(mapping.get('response_id')) if mapping.get('response_id') else '')
            name = normalize_value(row.get(mapping.get('name')) if mapping.get('name') else '')
            roll_number = normalize_value(row.get(mapping.get('roll_number')) if mapping.get('roll_number') else '')
            email = normalize_value(row.get(mapping.get('email')) if mapping.get('email') else '')
            phone = normalize_value(row.get(mapping.get('phone')) if mapping.get('phone') else '')
            branch = normalize_value(row.get(mapping.get('branch')) if mapping.get('branch') else '')
            registration_timestamp = parse_registration_timestamp(row.get(mapping.get('registration_timestamp')) if mapping.get('registration_timestamp') else '')

            if not name and not roll_number and not email:
                continue

            participant = None
            if response_id:
                participant = event.participants.filter(google_response_identifier=response_id).first()
            if not participant and roll_number:
                participant = event.participants.filter(roll_number=roll_number).first()
            if not participant and email:
                participant = event.participants.filter(email=email).first()
            if not participant and name and roll_number:
                participant = event.participants.filter(name=name, roll_number=roll_number).first()

            if participant is None:
                participant = Participant.objects.create(
                    event=event,
                    name=name or 'Unnamed Participant',
                    roll_number=roll_number or None,
                    email=email or None,
                    phone=phone or None,
                    branch=branch or None,
                    registration_timestamp=registration_timestamp,
                    google_response_identifier=response_id or None,
                    raw_registration_data=row,
                    source=ParticipantSource.GOOGLE_SHEETS,
                )
                Attendance.objects.get_or_create(participant=participant, defaults={'status': AttendanceStatus.ABSENT})
                result['new_records'] += 1
                continue

            attendance = getattr(participant, 'attendance', None)
            if attendance is None:
                Attendance.objects.create(participant=participant, status=AttendanceStatus.ABSENT)

            updated = False
            if response_id and not participant.google_response_identifier:
                participant.google_response_identifier = response_id
                updated = True
            for field_name, field_value in {
                'name': name or participant.name,
                'roll_number': roll_number or participant.roll_number,
                'email': email or participant.email,
                'phone': phone or participant.phone,
                'branch': branch or participant.branch,
                'registration_timestamp': registration_timestamp or participant.registration_timestamp,
            }.items():
                current_value = getattr(participant, field_name)
                if current_value != field_value:
                    setattr(participant, field_name, field_value)
                    updated = True
            if updated:
                participant.raw_registration_data = row
                participant.save(update_fields=['name', 'roll_number', 'email', 'phone', 'branch', 'registration_timestamp', 'google_response_identifier', 'raw_registration_data', 'updated_at'])
                result['updated_records'] += 1
            else:
                result['duplicate_records'] += 1

        sync_log.new_records = result['new_records']
        sync_log.updated_records = result['updated_records']
        sync_log.duplicate_records = result['duplicate_records']
        sync_log.completed_at = timezone.now()
        sync_log.status = 'SUCCESS'
        sync_log.save(update_fields=['new_records', 'updated_records', 'duplicate_records', 'completed_at', 'status'])

        if connection:
            connection.last_synced_at = sync_log.completed_at
            connection.sync_status = 'CONNECTED'
            connection.last_error = ''
            connection.column_mapping = mapping
            connection.save(update_fields=['last_synced_at', 'sync_status', 'last_error', 'column_mapping', 'updated_at'])

        return result
    except Exception as exc:
        sync_log.status = 'ERROR'
        sync_log.error_message = str(exc)
        sync_log.completed_at = timezone.now()
        sync_log.save(update_fields=['status', 'error_message', 'completed_at'])
        if connection:
            connection.sync_status = 'ERROR'
            connection.last_error = str(exc)
            connection.last_synced_at = sync_log.completed_at
            connection.save(update_fields=['sync_status', 'last_error', 'last_synced_at', 'updated_at'])
        raise
