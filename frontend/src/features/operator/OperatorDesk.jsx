import { useCallback, useEffect, useState } from 'react'
import { request } from '../../api/client'
import Notice from '../../components/Notice'
import AddAircraftForm from './AddAircraftForm'
import AircraftFleet from './AircraftFleet'
import FlightsTable from './FlightsTable'
import MaintenancePanel from './MaintenancePanel'
import OperatorOverview from './OperatorOverview'
import PilotsTable from './PilotsTable'

const OPERATOR_DATA_PATHS = [
  '/operator/me',
  '/operator/aircraft',
  '/operator/maintenance',
  '/operator/pilots',
  '/operator/flights',
  '/aircraft-types',
]

const tabs = [
  ['overview', 'Overview'],
  ['fleet', 'Aircraft fleet'],
  ['maintenance', 'Maintenance'],
  ['pilots', 'Pilots'],
  ['flights', 'Flights'],
  ['add', 'Add aircraft'],
]

export default function OperatorDesk({ token, busy, setMessage, message, initialTab = 'overview' }) {
  const [tab, setTab] = useState(initialTab)
  const [profile, setProfile] = useState(null)
  const [aircraft, setAircraft] = useState([])
  const [maintenance, setMaintenance] = useState([])
  const [pilots, setPilots] = useState([])
  const [flights, setFlights] = useState([])
  const [serviceCosts, setServiceCosts] = useState({})
  const [aircraftTypes, setAircraftTypes] = useState([])
  const [newAircraft, setNewAircraft] = useState({ registration_no: '', type_id: '' })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const [operator, fleet, dueForService, crew, bookings, types] = await Promise.all(
      OPERATOR_DATA_PATHS.map((path) => request(path, { token })),
    )
    setProfile(operator)
    setAircraft(fleet)
    setMaintenance(dueForService)
    setPilots(crew)
    setFlights(bookings)
    setAircraftTypes(types)
  }, [token])

  useEffect(() => {
    load().catch((error) => setMessage(error.message))
  }, [load, setMessage])

  async function markServiced(item) {
    setSaving(true)
    setMessage('')
    try {
      await request(`/operator/aircraft/${item.aircraft_id}/service`, {
        token,
        method: 'POST',
        body: JSON.stringify({ cost: Number(serviceCosts[item.aircraft_id] || 0) }),
      })
      setMessage(`${item.registration_no} marked as serviced.`)
      await load()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setSaving(false)
    }
  }

  async function addAircraft(event) {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const created = await request('/operator/aircraft', {
        token,
        method: 'POST',
        body: JSON.stringify({
          registration_no: newAircraft.registration_no,
          type_id: Number(newAircraft.type_id),
        }),
      })
      setMessage(`${created.registration_no} added to your fleet.`)
      setNewAircraft({ registration_no: '', type_id: '' })
      await load()
      setTab('fleet')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="operator-section" id="operator">
      <div className="operator-heading">
        <div>
          <div className="eyebrow"><span/> OPERATOR DESK</div>
          <h2>{profile?.name || 'Your operator desk'}</h2>
          <p>Manage your aircraft and maintenance; view your pilots and customer flights.</p>
        </div>
        <span className="operator-license">License {profile?.license_no || '—'}</span>
      </div>

      <Notice onDismiss={() => setMessage('')}>{message}</Notice>

      <nav className="operator-tabs" aria-label="Operator sections">
        {tabs.map(([id, label]) => (
          <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>

      {tab === 'overview' && (
        <OperatorOverview aircraft={aircraft} maintenance={maintenance} pilots={pilots}
          flights={flights} onSelectTab={setTab}/>
      )}
      {tab === 'fleet' && <AircraftFleet aircraft={aircraft}/>}
      {tab === 'maintenance' && (
        <MaintenancePanel aircraft={maintenance} serviceCosts={serviceCosts} saving={saving}
          onCostChange={(id, value) => setServiceCosts((current) => ({ ...current, [id]: value }))}
          onService={markServiced}/>
      )}
      {tab === 'pilots' && <PilotsTable pilots={pilots}/>}
      {tab === 'flights' && <FlightsTable flights={flights}/>}
      {tab === 'add' && (
        <AddAircraftForm aircraftTypes={aircraftTypes} aircraft={newAircraft} saving={saving} busy={busy}
          onSubmit={addAircraft} onChange={setNewAircraft}/>
      )}
    </section>
  )
}
