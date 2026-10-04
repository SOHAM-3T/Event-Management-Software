import {
  Activity,
  CalendarDays,
  CheckCircle2,
  CircleDashed,
  Clock3,
  LogOut,
  Pencil,
  RefreshCcw,
  Trash2,
  UserCheck,
  Users,
} from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import axios from 'axios'
import './App.css'

const getToken = () => localStorage.getItem('eventtrack_token')

const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = new axios.AxiosHeaders({
      ...(config.headers as Record<string, string>),
      Authorization: `Bearer ${token}`,
    })
  }
  return config
})

type EventItem = {
  id: string
  name: string
  description?: string | null
  date: string
  start_time?: string | null
  end_time?: string | null
  venue?: string | null
  status: string
  registration_source: string
}

type EventFormState = {
  name: string
  description: string
  date: string
  start_time: string
  end_time: string
  venue: string
  status: 'UPCOMING' | 'LIVE' | 'COMPLETED'
  registration_source: 'GOOGLE_FORMS' | 'EXCEL' | 'MANUAL'
}

type DashboardStats = {
  total_registered: number
  present: number
  absent: number
  attendance_percentage: number
}

type ParticipantItem = {
  id: string
  name: string
  roll_number?: string | null
  email?: string | null
  branch?: string | null
  source: string
  attendance_status: 'PRESENT' | 'ABSENT'
  checked_in_at?: string | null
}

const createEmptyEventForm = (): EventFormState => ({
  name: '',
  description: '',
  date: new Date().toISOString().slice(0, 10),
  start_time: '10:00',
  end_time: '13:00',
  venue: '',
  status: 'UPCOMING',
  registration_source: 'GOOGLE_FORMS',
})

const buildSampleSyncPayload = () => JSON.stringify([
  {
    'Response ID': 'sync-001',
    Timestamp: '2026-10-05 09:00:00',
    Name: 'Aanya Patel',
    'Roll Number': '21CS104',
    Email: 'aanya@example.com',
    'Phone Number': '9001122334',
    Branch: 'CSE',
  },
  {
    'Response ID': 'sync-002',
    Timestamp: '2026-10-05 09:10:00',
    Name: 'Kabir Menon',
    'Roll Number': '21CS222',
    Email: 'kabir@example.com',
    'Phone Number': '9001122335',
    Branch: 'ECE',
  },
], null, 2)

const formatDate = (value?: string) => {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

const formatTimeRange = (start?: string | null, end?: string | null) => {
  if (!start && !end) return '—'
  return `${start ?? '—'}${start && end ? ' - ' : ''}${end ?? ''}`
}

function App() {
  const [token, setToken] = useState<string | null>(getToken())
  const [events, setEvents] = useState<EventItem[]>([])
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [dashboard, setDashboard] = useState<{ stats: DashboardStats; event: EventItem } | null>(null)
  const [participants, setParticipants] = useState<ParticipantItem[]>([])
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin123')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const [eventForm, setEventForm] = useState<EventFormState>(createEmptyEventForm())
  const [eventFormOpen, setEventFormOpen] = useState(false)
  const [editingEventId, setEditingEventId] = useState<string | null>(null)
  const [syncRows, setSyncRows] = useState(buildSampleSyncPayload())
  const [spreadsheetId, setSpreadsheetId] = useState('')
  const [sheetName, setSheetName] = useState('Sheet1')

  const loadEvents = async () => {
    const response = await api.get('/events/')
    const nextEvents = response.data as EventItem[]
    setEvents(nextEvents)
    if (nextEvents.length && (!selectedEventId || !nextEvents.some((event) => event.id === selectedEventId))) {
      setSelectedEventId(nextEvents[0].id)
    }
  }

  const loadDashboard = async (eventId: string) => {
    setLoading(true)
    try {
      const [dashboardResponse, participantsResponse] = await Promise.all([
        api.get(`/events/${eventId}/dashboard/`),
        api.get(`/events/${eventId}/participants/`),
      ])

      setDashboard(dashboardResponse.data)
      setParticipants(participantsResponse.data as ParticipantItem[])
    } catch {
      setError('Unable to load the selected event right now.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!token) return
    void loadEvents().catch(() => setError('Unable to load events.'))
  }, [token])

  useEffect(() => {
    if (!token || !selectedEventId) return
    void loadDashboard(selectedEventId)
  }, [selectedEventId, token])

  useEffect(() => {
    if (!selectedEventId) return
    const savedConfig = localStorage.getItem(`eventtrack_sheet_${selectedEventId}`)
    if (!savedConfig) {
      setSpreadsheetId('')
      setSheetName('Sheet1')
      return
    }

    try {
      const config = JSON.parse(savedConfig) as { spreadsheetId?: string; sheetName?: string }
      setSpreadsheetId(config.spreadsheetId ?? '')
      setSheetName(config.sheetName ?? 'Sheet1')
    } catch {
      localStorage.removeItem(`eventtrack_sheet_${selectedEventId}`)
    }
  }, [selectedEventId])

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault()
    setError('')

    try {
      const response = await axios.post('/api/auth/login/', { username, password })
      const accessToken = response.data.access
      localStorage.setItem('eventtrack_token', accessToken)
      setToken(accessToken)
    } catch {
      setError('Invalid username or password. Use the admin credentials created locally.')
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('eventtrack_token')
    setToken(null)
    setEvents([])
    setDashboard(null)
    setParticipants([])
    setSelectedEventId(null)
    setError('')
    setNotice('')
  }

  const openCreateEventForm = () => {
    setEventForm(createEmptyEventForm())
    setEditingEventId(null)
    setEventFormOpen(true)
  }

  const openEditEventForm = (event: EventItem) => {
    setEventForm({
      name: event.name,
      description: event.description ?? '',
      date: event.date,
      start_time: event.start_time ?? '10:00',
      end_time: event.end_time ?? '13:00',
      venue: event.venue ?? '',
      status: event.status as 'UPCOMING' | 'LIVE' | 'COMPLETED',
      registration_source: event.registration_source as 'GOOGLE_FORMS' | 'EXCEL' | 'MANUAL',
    })
    setEditingEventId(event.id)
    setEventFormOpen(true)
  }

  const handleEventSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')

    try {
      const payload = {
        ...eventForm,
        description: eventForm.description || null,
        venue: eventForm.venue || null,
      }

      if (editingEventId) {
        await api.put(`/events/${editingEventId}/`, payload)
      } else {
        const response = await api.post('/events/', payload)
        setSelectedEventId(response.data.id)
      }

      setEventFormOpen(false)
      setNotice(editingEventId ? 'Event updated successfully.' : 'Event created successfully.')
      await loadEvents()
    } catch {
      setError('Unable to save this event. Check the details and try again.')
    }
  }

  const handleDeleteEvent = async (eventId: string) => {
    if (!window.confirm('Delete this event and its participant records?')) return

    try {
      await api.delete(`/events/${eventId}/`)
      setNotice('Event deleted successfully.')
      setEventFormOpen(false)
      const nextEvents = events.filter((event) => event.id !== eventId)
      setEvents(nextEvents)
      if (selectedEventId === eventId) {
        setSelectedEventId(nextEvents[0]?.id ?? null)
      }
    } catch {
      setError('Unable to delete this event right now.')
    }
  }

  const handleAttendanceToggle = async (participantId: string, currentStatus: 'PRESENT' | 'ABSENT') => {
    if (!selectedEventId) return

    const nextStatus = currentStatus === 'PRESENT' ? 'ABSENT' : 'PRESENT'
    await api.patch(`/events/${selectedEventId}/participants/${participantId}/attendance/`, {
      status: nextStatus,
    })
    void loadDashboard(selectedEventId)
  }

  const handleSyncRegistrations = async () => {
    if (!selectedEventId) return

    try {
      const payload: Record<string, unknown> = {
        sheet_name: sheetName || 'Sheet1',
      }

      if (spreadsheetId.trim()) {
        payload.spreadsheet_id = spreadsheetId.trim()
      } else {
        const rows = JSON.parse(syncRows)
        if (!Array.isArray(rows) || rows.length === 0) {
          throw new Error('Rows must be a non-empty array.')
        }

        payload.rows = rows
        payload.column_mapping = {
          response_id: 'Response ID',
          name: 'Name',
          roll_number: 'Roll Number',
          email: 'Email',
          phone: 'Phone Number',
          branch: 'Branch',
          registration_timestamp: 'Timestamp',
        }
      }

      const response = await api.post(`/events/${selectedEventId}/sync/`, payload)
      if (spreadsheetId.trim()) {
        localStorage.setItem(`eventtrack_sheet_${selectedEventId}`, JSON.stringify({
          spreadsheetId: spreadsheetId.trim(),
          sheetName: sheetName || 'Sheet1',
        }))
      }

      setNotice(
        `Sync complete: ${response.data.result.new_records ?? 0} new, ${response.data.result.updated_records ?? 0} updated.`
      )
      await loadDashboard(selectedEventId)
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null
      setError(typeof detail === 'string'
        ? detail
        : 'Sync failed. Check your spreadsheet URL or ID, service-account access, and sheet tab name.')
    }
  }

  const filteredParticipants = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return participants

    return participants.filter((participant) => {
      const candidate = `${participant.name} ${participant.roll_number ?? ''} ${participant.email ?? ''}`.toLowerCase()
      return candidate.includes(term)
    })
  }, [participants, search])

  const activeEvent = dashboard?.event ?? events.find((event) => event.id === selectedEventId) ?? null

  const stats = [
    { label: 'Total Registered', value: String(dashboard?.stats.total_registered ?? 0), icon: Users, tone: 'blue' },
    { label: 'Present', value: String(dashboard?.stats.present ?? 0), icon: UserCheck, tone: 'green' },
    { label: 'Absent', value: String(dashboard?.stats.absent ?? 0), icon: CircleDashed, tone: 'amber' },
    { label: 'Attendance', value: `${dashboard?.stats.attendance_percentage ?? 0}%`, icon: Activity, tone: 'purple' },
  ]

  if (!token) {
    return (
      <div className="auth-shell">
        <form className="auth-card" onSubmit={handleLogin}>
          <p className="eyebrow">EventTrack</p>
          <h1>Sign in</h1>
          <p className="auth-subtitle">Use your Django admin account to access the event dashboard.</p>

          <label>
            <span>Username</span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" />
          </label>

          <label>
            <span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="admin123" />
          </label>

          {error ? <div className="error-banner">{error}</div> : null}

          <button type="submit" className="primary-button auth-button">Log in</button>
        </form>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">EventTrack</p>
          <h1>Registration & attendance dashboard</h1>
        </div>
        <div className="topbar-actions">
          <button type="button" className="ghost-button" onClick={handleLogout}>
            <LogOut size={16} />
            Log out
          </button>
        </div>
      </header>

      {activeEvent && (
        <section className="hero-panel">
          <div>
            <span className={`status-pill ${activeEvent.status.toLowerCase()}`}>{activeEvent.status}</span>
            <h2>{activeEvent.name}</h2>
            <div className="meta-row">
              <span><CalendarDays size={16} /> {formatDate(activeEvent.date)}</span>
              <span><Clock3 size={16} /> {formatTimeRange(activeEvent.start_time, activeEvent.end_time)}</span>
              <span>{activeEvent.venue ?? 'Venue TBD'}</span>
            </div>
          </div>

          <div className="hero-actions">
            <button type="button" className="ghost-button" onClick={() => openEditEventForm(activeEvent)}>
              <Pencil size={16} />
              Edit event
            </button>
            <button type="button" className="ghost-button danger-button" onClick={() => handleDeleteEvent(activeEvent.id)}>
              <Trash2 size={16} />
              Delete
            </button>
          </div>
        </section>
      )}

      {notice ? <div className="success-banner">{notice}</div> : null}
      {error ? <div className="error-banner">{error}</div> : null}

      <section className="stats-grid">
        {stats.map(({ label, value, icon: Icon, tone }) => (
          <article key={label} className={`stat-card ${tone}`}>
            <div className="stat-icon">
              <Icon size={18} />
            </div>
            <div>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <div className="panel left-panel">
          <div className="panel-header">
            <h3>Recent events</h3>
            <button type="button" className="primary-button small-button" onClick={openCreateEventForm}>
              + New event
            </button>
          </div>
          <div className="event-list">
            {events.map((event) => (
              <button
                type="button"
                key={event.id}
                className={`event-item ${selectedEventId === event.id ? 'selected' : ''}`}
                onClick={() => setSelectedEventId(event.id)}
              >
                <div>
                  <h4>{event.name}</h4>
                  <small>{formatDate(event.date)}</small>
                </div>
                <span className={`event-badge ${event.status.toLowerCase()}`}>{event.status}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="panel right-panel">
          <div className="panel-header">
            <h3>Quick check-in</h3>
          </div>
          <div className="quick-checkin">
            <label>
              <span>Search by name / roll no / email</span>
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search participants" />
            </label>
            <div className="person-preview">
              <div>
                <strong>{filteredParticipants[0]?.name ?? 'No match'}</strong>
                <small>{filteredParticipants[0] ? `${filteredParticipants[0].roll_number ?? 'No roll'} • ${filteredParticipants[0].branch ?? 'Unspecified'}` : 'Try another search'}</small>
              </div>
              {filteredParticipants[0] ? (
                <button type="button" className="checkin-button" onClick={() => handleAttendanceToggle(filteredParticipants[0].id, filteredParticipants[0].attendance_status)}>
                  {filteredParticipants[0].attendance_status === 'PRESENT' ? 'Mark Absent' : 'Check In'}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <section className="panel sync-panel">
        <div className="panel-header">
          <h3>Registration sync</h3>
          <button type="button" className="primary-button small-button" onClick={handleSyncRegistrations}>
            <RefreshCcw size={16} />
            Sync rows
          </button>
        </div>
        <div className="sync-config-grid">
          <label>
            <span>Google Sheet URL or ID</span>
            <input
              value={spreadsheetId}
              onChange={(e) => setSpreadsheetId(e.target.value)}
              placeholder="Paste the full Google Sheets URL or ID"
            />
          </label>
          <label>
            <span>Sheet name</span>
            <input value={sheetName} onChange={(e) => setSheetName(e.target.value)} placeholder="Sheet1" />
          </label>
        </div>
        <textarea
          value={syncRows}
          onChange={(e) => setSyncRows(e.target.value)}
          rows={8}
          className="sync-textarea"
          placeholder='[{"Response ID":"..."}]'
        />
      </section>

      <section className="panel table-panel">
        <div className="panel-header">
          <h3>Participant list</h3>
        </div>

        {loading ? (
          <div className="loading-state">Loading participants...</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Roll</th>
                <th>Email</th>
                <th>Branch</th>
                <th>Attendance</th>
                <th>Checked in</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredParticipants.map((person) => (
                <tr key={person.id}>
                  <td>{person.name}</td>
                  <td>{person.roll_number ?? '—'}</td>
                  <td>{person.email ?? '—'}</td>
                  <td>{person.branch ?? '—'}</td>
                  <td>
                    <span className={`attendance-pill ${person.attendance_status.toLowerCase()}`}>
                      {person.attendance_status}
                    </span>
                  </td>
                  <td>{person.checked_in_at ? formatDate(person.checked_in_at) : '—'}</td>
                  <td>
                    <button type="button" className="table-button" onClick={() => handleAttendanceToggle(person.id, person.attendance_status)}>
                      {person.attendance_status === 'PRESENT' ? 'Mark absent' : 'Mark present'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="bottom-strip">
        <div className="mini-card">
          <CheckCircle2 size={18} />
          <span>Google Form registration sync is enabled.</span>
        </div>
        <div className="mini-card">
          <CalendarDays size={18} />
          <span>Attendance updates are saved in real time.</span>
        </div>
      </section>

      {eventFormOpen && (
        <div className="modal-backdrop" onClick={() => setEventFormOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="panel-header">
              <h3>{editingEventId ? 'Edit event' : 'Create new event'}</h3>
              <button type="button" className="ghost-button" onClick={() => setEventFormOpen(false)}>Close</button>
            </div>

            <form onSubmit={handleEventSubmit} className="event-form">
              <div className="form-grid">
                <label>
                  <span>Event name</span>
                  <input value={eventForm.name} onChange={(e) => setEventForm({ ...eventForm, name: e.target.value })} required />
                </label>

                <label>
                  <span>Venue</span>
                  <input value={eventForm.venue} onChange={(e) => setEventForm({ ...eventForm, venue: e.target.value })} />
                </label>

                <label>
                  <span>Date</span>
                  <input type="date" value={eventForm.date} onChange={(e) => setEventForm({ ...eventForm, date: e.target.value })} required />
                </label>

                <label>
                  <span>Status</span>
                  <select value={eventForm.status} onChange={(e) => setEventForm({ ...eventForm, status: e.target.value as EventFormState['status'] })}>
                    <option value="UPCOMING">Upcoming</option>
                    <option value="LIVE">Live</option>
                    <option value="COMPLETED">Completed</option>
                  </select>
                </label>

                <label>
                  <span>Start time</span>
                  <input type="time" value={eventForm.start_time} onChange={(e) => setEventForm({ ...eventForm, start_time: e.target.value })} />
                </label>

                <label>
                  <span>End time</span>
                  <input type="time" value={eventForm.end_time} onChange={(e) => setEventForm({ ...eventForm, end_time: e.target.value })} />
                </label>

                <label>
                  <span>Registration source</span>
                  <select value={eventForm.registration_source} onChange={(e) => setEventForm({ ...eventForm, registration_source: e.target.value as EventFormState['registration_source'] })}>
                    <option value="GOOGLE_FORMS">Google Forms</option>
                    <option value="EXCEL">Excel</option>
                    <option value="MANUAL">Manual</option>
                  </select>
                </label>

                <label className="full-width">
                  <span>Description</span>
                  <textarea value={eventForm.description} rows={4} onChange={(e) => setEventForm({ ...eventForm, description: e.target.value })} />
                </label>
              </div>

              <div className="form-actions">
                <button type="button" className="ghost-button" onClick={() => setEventFormOpen(false)}>Cancel</button>
                <button type="submit" className="primary-button">{editingEventId ? 'Save changes' : 'Create event'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
