# Event-Management-Software

## Connect a Google Form response sheet (local development)

EventTrack reads the spreadsheet when you click **Sync rows** in the dashboard. It does not continuously poll the sheet in the background. The spreadsheet ID and tab name are remembered per event in this browser after a successful sync.

### 1. Get the Google Sheet ID

Open the response spreadsheet. Its URL looks like:

`https://docs.google.com/spreadsheets/d/1AbCDefGhIJklMNopQRstuVWxyz1234567890/edit#gid=0`

The **spreadsheet ID** is the text between `/d/` and `/edit`:

`1AbCDefGhIJklMNopQRstuVWxyz1234567890`

Do not include `/edit`, `#gid=...`, or the entire URL. In Google Forms, open **Responses** and click the green Sheets icon to open or create the linked response spreadsheet. Use the tab name shown at the bottom of that spreadsheet, commonly `Form Responses 1`.

### 2. Create service-account credentials

1. In Google Cloud Console, select or create a project and enable the **Google Sheets API**.
2. Create a service account and download a JSON key for it.
3. Copy the downloaded key into `backend/credentials/google-service-account.json` (create the `credentials` directory if needed). Keep this key private; the directory is excluded from Git.
4. Copy `backend/.env.example` to `backend/.env`. Keep `GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google-service-account.json` in that file.
5. Open the downloaded JSON and copy its `client_email`. Share the response spreadsheet with that email as a **Viewer**. The service account must have access to the spreadsheet.

### 3. Sync from EventTrack

Start the Django backend and Vite frontend, sign in, select an event, then enter the spreadsheet ID and tab name in **Registration sync** and click **Sync rows**. The backend reads the header row and registrations directly from Google Sheets; subsequent clicks for that event reuse the saved sheet configuration. The existing JSON rows input remains available when no spreadsheet ID is supplied.

The integration only requests read-only spreadsheet access. It imports new/changed registration data and preserves attendance statuses already recorded in EventTrack.
