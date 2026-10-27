import { useEffect, useMemo, useState } from 'react'
import GlobeFlight from './GlobeFlight'
import Navbar from './Navbar'
import './App.css'

const API = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
const money = (value) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value || 0)
const localDateTime = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`

async function request(path, { token, ...options } = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  if (response.status === 204) return null
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Something went wrong. Please try again.')
  return data
}

function Icon({ name, size = 20 }) {
  const paths = {
    plane: <><path d="m2 16 20-6-20-6 4 6-4 6Z"/><path d="M6 10h8"/></>,
    arrow: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>,
    pin: <><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

function OperatorDesk({ token, locations, dateMin, busy, setBusy, setMessage, message, initialTab = 'overview' }) {
  const [tab, setTab] = useState(initialTab)
  const [profile, setProfile] = useState(null)
  const [aircraft, setAircraft] = useState([])
  const [maintenance, setMaintenance] = useState([])
  const [pilots, setPilots] = useState([])
  const [flights, setFlights] = useState([])
  const [serviceCosts, setServiceCosts] = useState({})
  const [flight, setFlight] = useState({ aircraft_id: '', origin_id: '', dest_id: '', departure_time: dateMin, passengers: 1, customer_name: '', customer_email: '', customer_phone: '', customer_id_proof: '' })
  const [saving, setSaving] = useState(false)
  const load = async () => {
    const [p, a, m, crew, f] = await Promise.all(['/operator/me','/operator/aircraft','/operator/maintenance','/operator/pilots','/operator/flights'].map((path) => request(path, { token })))
    setProfile(p); setAircraft(a); setMaintenance(m); setPilots(crew); setFlights(f)
  }
  useEffect(() => { load().catch((error) => setMessage(error.message)) }, [token])
  useEffect(() => { setFlight((current) => ({ ...current, departure_time: current.departure_time || dateMin })) }, [dateMin])
  const placeLabel = (id) => locations.find((place) => String(place.location_id) === String(id))?.code || '—'
  async function markServiced(item) {
    setSaving(true); setMessage('')
    try { await request(`/operator/aircraft/${item.aircraft_id}/service`, { token, method: 'POST', body: JSON.stringify({ cost: Number(serviceCosts[item.aircraft_id] || 0) }) }); setMessage(`${item.registration_no} marked as serviced.`); await load() }
    catch (error) { setMessage(error.message) } finally { setSaving(false) }
  }
  async function addFlight(event) {
    event.preventDefault(); setSaving(true); setMessage('')
    try { const body = { ...flight, aircraft_id: Number(flight.aircraft_id), origin_id: Number(flight.origin_id), dest_id: Number(flight.dest_id), passengers: Number(flight.passengers) }; const created = await request('/operator/flights', { token, method: 'POST', body: JSON.stringify(body) }); setMessage(`Flight booking #${created.booking_id} added.`); setFlight((v) => ({ ...v, customer_name: '', customer_email: '', customer_phone: '', customer_id_proof: '' })); await load(); setTab('flights') }
    catch (error) { setMessage(error.message) } finally { setSaving(false) }
  }
  const nav = [['overview','Overview'],['fleet','Aircraft fleet'],['maintenance','Maintenance'],['pilots','Pilots'],['flights','Flights'],['add','Add a flight']]
  return <section className="operator-section" id="operator">
    <div className="operator-heading"><div><div className="eyebrow"><span/> OPERATOR DESK</div><h2>{profile?.name || 'Your operator desk'}</h2><p>Manage your aircraft, pilots, maintenance and customer flights.</p></div><span className="operator-license">License {profile?.license_no || '—'}</span></div>
    {message && <div className="notice" role="status">{message}<button onClick={() => setMessage('')} aria-label="Dismiss">×</button></div>}
    <nav className="operator-tabs" aria-label="Operator sections">{nav.map(([id,label]) => <button key={id} className={tab===id?'active':''} onClick={() => setTab(id)}>{label}</button>)}</nav>
    {tab === 'overview' && <><div className="operator-stats"><button onClick={() => setTab('fleet')}><strong>{aircraft.length}</strong><span>Aircraft in fleet</span></button><button onClick={() => setTab('maintenance')}><strong>{maintenance.length}</strong><span>Need maintenance</span></button><button onClick={() => setTab('pilots')}><strong>{pilots.length}</strong><span>Pilots</span></button><button onClick={() => setTab('flights')}><strong>{flights.length}</strong><span>Booked flights</span></button></div><div className="operator-panels"><article><div className="operator-panel-title"><h3>Maintenance attention</h3><button onClick={() => setTab('maintenance')}>View all →</button></div>{maintenance.length ? maintenance.slice(0,3).map((item) => <p className="operator-summary-row" key={item.aircraft_id}><b>{item.registration_no}</b><span>{item.hours_since_service} hours since service</span></p>) : <p className="empty-copy">All aircraft are within their service interval.</p>}</article><article><div className="operator-panel-title"><h3>Fleet snapshot</h3><button onClick={() => setTab('fleet')}>View fleet →</button></div>{aircraft.slice(0,3).map((item) => <p className="operator-summary-row" key={item.aircraft_id}><b>{item.registration_no}</b><span>{item.type_model} · {item.status}</span></p>)}</article></div></>}
    {tab === 'fleet' && <div className="operator-table-wrap"><h3>Aircraft fleet</h3><table className="operator-table"><thead><tr><th>Registration</th><th>Aircraft</th><th>Seats</th><th>Status</th><th>Hours to service</th></tr></thead><tbody>{aircraft.map((item) => <tr key={item.aircraft_id}><td>{item.registration_no}</td><td>{item.type_model}</td><td>{item.seats}</td><td><span className={`status ${item.status==='Available'?'status-confirmed':''}`}>{item.status}</span></td><td>{Number(item.service_due_in_hours).toFixed(1)}</td></tr>)}</tbody></table>{!aircraft.length && <p className="empty-copy">No aircraft are assigned to this operator yet.</p>}</div>}
    {tab === 'maintenance' && <div className="operator-table-wrap"><h3>Maintenance due</h3><p className="operator-subcopy">Aircraft appear here when marked for maintenance or within 10% of their service interval.</p>{maintenance.length ? <div className="maintenance-list">{maintenance.map((item) => <article key={item.aircraft_id}><div><b>{item.registration_no} · {item.type_model}</b><small>{Number(item.hours_since_service).toFixed(1)} hours since last service · {item.status}</small></div><label>Cost<input aria-label={`Service cost for ${item.registration_no}`} type="number" min="0" step="0.01" value={serviceCosts[item.aircraft_id] || ''} onChange={(e) => setServiceCosts({ ...serviceCosts, [item.aircraft_id]: e.target.value })} placeholder="0.00"/></label><button disabled={saving} onClick={() => markServiced(item)}>Record service</button></article>)}</div> : <p className="empty-copy">No aircraft currently need maintenance.</p>}</div>}
    {tab === 'pilots' && <div className="operator-table-wrap"><h3>Your pilots</h3><table className="operator-table"><thead><tr><th>Name</th><th>License</th><th>Rating</th><th>Experience</th><th>Status</th></tr></thead><tbody>{pilots.map((pilot) => <tr key={pilot.pilot_id}><td>{pilot.name}</td><td>{pilot.license_no}</td><td>{pilot.category_rating}</td><td>{pilot.experience_hours} hrs</td><td>{pilot.status}</td></tr>)}</tbody></table>{!pilots.length && <p className="empty-copy">No pilots are assigned to this operator yet.</p>}</div>}
    {tab === 'flights' && <div className="operator-table-wrap"><h3>Customer flights</h3><table className="operator-table"><thead><tr><th>Route</th><th>Customer</th><th>Aircraft</th><th>Departure</th><th>Status</th><th>Fare due</th></tr></thead><tbody>{flights.map((item) => <tr key={item.booking_id}><td>{item.origin_code} → {item.dest_code}</td><td>{item.customer_name}</td><td>{item.registration_no}</td><td>{new Date(item.departure_time).toLocaleString()}</td><td>{item.status}</td><td>{money(item.balance_due)}</td></tr>)}</tbody></table>{!flights.length && <p className="empty-copy">No customer flights booked yet.</p>}</div>}
    {tab === 'add' && <form className="operator-flight-form" onSubmit={addFlight}><h3>Add a customer flight</h3><p>Choose one of your available aircraft and enter the customer’s booking details.</p><div className="operator-form-grid"><label>Aircraft<select required value={flight.aircraft_id} onChange={(e) => setFlight({...flight, aircraft_id:e.target.value})}><option value="">Choose aircraft</option>{aircraft.filter((a)=>a.status==='Available').map((a)=><option key={a.aircraft_id} value={a.aircraft_id}>{a.registration_no} · {a.type_model} ({a.seats} seats)</option>)}</select></label><label>Departure airport<select required value={flight.origin_id} onChange={(e)=>setFlight({...flight,origin_id:e.target.value})}><option value="">Choose departure</option>{locations.map((p)=><option key={p.location_id} value={p.location_id}>{p.city} · {p.code}</option>)}</select></label><label>Arrival airport<select required value={flight.dest_id} onChange={(e)=>setFlight({...flight,dest_id:e.target.value})}><option value="">Choose destination</option>{locations.map((p)=><option key={p.location_id} value={p.location_id}>{p.city} · {p.code}</option>)}</select></label><label>Departure date and time<input type="datetime-local" min={dateMin} required value={flight.departure_time} onChange={(e)=>setFlight({...flight,departure_time:e.target.value})}/></label><label>Passengers<input type="number" min="1" required value={flight.passengers} onChange={(e)=>setFlight({...flight,passengers:e.target.value})}/></label><label>Customer name<input required value={flight.customer_name} onChange={(e)=>setFlight({...flight,customer_name:e.target.value})}/></label><label>Customer email<input type="email" required value={flight.customer_email} onChange={(e)=>setFlight({...flight,customer_email:e.target.value})}/></label><label>Customer phone<input required value={flight.customer_phone} onChange={(e)=>setFlight({...flight,customer_phone:e.target.value})}/></label><label>Customer ID proof<input required value={flight.customer_id_proof} onChange={(e)=>setFlight({...flight,customer_id_proof:e.target.value})}/></label></div><button className="primary-button" disabled={saving || busy}>{saving?'Adding flight…':'Add flight'} <Icon name="arrow" size={17}/></button></form>}
  </section>
}

function App() {
  const [scrollProgress, setScrollProgress] = useState(0)
  const [token, setToken] = useState(() => sessionStorage.getItem('charter_token'))
  const [user, setUser] = useState(null)
  const [locations, setLocations] = useState([])
  const [rules, setRules] = useState({ min_lead_minutes: 30, max_passengers: 500 })
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [departure, setDeparture] = useState(() => localDateTime(new Date(Date.now() + 86400000)))
  const [passengers, setPassengers] = useState(2)
  const [results, setResults] = useState([])
  const [bookings, setBookings] = useState([])
  const [payments, setPayments] = useState({})
  const [activeView, setActiveView] = useState('search')
  const [authOpen, setAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', name: '', phone: '', id_proof: '', license_no: '', city: '', service_interval_hrs: '' })
  const [accountType, setAccountType] = useState('customer')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [searchDone, setSearchDone] = useState(false)
  const [selectedBooking, setSelectedBooking] = useState(null)

  useEffect(() => {
    Promise.all([request('/locations?limit=500'), request('/meta')]).then(([places, meta]) => {
      setLocations(places); setRules(meta.booking_rules)
      if (places.length > 1) { setOrigin(String(places[0].location_id)); setDestination(String(places[1].location_id)) }
    }).catch((error) => setMessage(error.message))
  }, [])

  useEffect(() => {
    if (!token) { setUser(null); return }
    request('/auth/me', { token }).then((current) => { setUser(current); if (current.role === 'operator') setActiveView('operator') }).catch(() => { sessionStorage.removeItem('charter_token'); setToken(null) })
  }, [token])

  const dateMin = useMemo(() => localDateTime(new Date(Date.now() + rules.min_lead_minutes * 60000)), [rules.min_lead_minutes])
  const placeName = (id) => locations.find((place) => String(place.location_id) === String(id))

  async function handleSearch(event) {
    event.preventDefault(); setMessage('')
    if (!token) { setAuthOpen(true); setMessage('Sign in to see available aircraft and fares.'); return }
    if (!origin || !destination || origin === destination) { setMessage('Choose two different destinations.'); return }
    setBusy(true); setResults([]); setSearchDone(false)
    try {
      const params = new URLSearchParams({ origin_id: origin, dest_id: destination, departure_time: departure, passengers })
      setResults(await request(`/search?${params}`, { token })); setSearchDone(true)
    } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function handleAuth(event) {
    event.preventDefault(); setBusy(true); setMessage('')
    try {
      const isOperator = accountType === 'operator'
      const payload = authMode === 'login'
        ? { email: form.email, password: form.password, ...(isOperator ? { license_no: form.license_no } : {}) }
        : isOperator
          ? { name: form.name, license_no: form.license_no, email: form.email, password: form.password, phone: form.phone, city: form.city, ...(form.service_interval_hrs ? { service_interval_hrs: Number(form.service_interval_hrs) } : {}) }
          : { name: form.name, email: form.email, password: form.password, phone: form.phone, id_proof: form.id_proof }
      const endpoint = isOperator ? `/auth/operator/${authMode === 'login' ? 'login' : 'register'}` : `/auth/${authMode === 'login' ? 'login' : 'register'}`
      const data = await request(endpoint, { method: 'POST', body: JSON.stringify(payload) })
      sessionStorage.setItem('charter_token', data.access_token); setToken(data.access_token); setUser(data.user); setAuthOpen(false); setActiveView(data.user.role === 'operator' ? 'operator' : 'search'); setMessage(data.user.role === 'operator' ? 'Welcome to your operator desk.' : 'You’re signed in. Search available flights to get started.')
    } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function bookFlight(flight) {
    if (!user) { setAuthOpen(true); return }
    setBusy(true); setMessage('')
    try {
      const booking = await request('/bookings', { token, method: 'POST', body: JSON.stringify({ aircraft_id: flight.aircraft_id, origin_id: Number(origin), dest_id: Number(destination), departure_time: departure, passengers: Number(passengers) }) })
      setSelectedBooking(booking); await loadBookings(); setActiveView('bookings'); setMessage(`Flight reserved. Booking #${booking.booking_id} is pending payment.`)
    } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function loadBookings() {
    if (!token) { setAuthOpen(true); return }
    setBusy(true)
    try { setBookings(await request('/bookings?limit=100', { token })) } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function payBooking(booking) {
    setBusy(true); setMessage('')
    try {
      await request(`/bookings/${booking.booking_id}/payments`, { token, method: 'POST', body: JSON.stringify({ amount: Number(booking.balance_due), method: payments[booking.booking_id] || 'Card' }) })
      setMessage(`Payment recorded for booking #${booking.booking_id}.`); await loadBookings()
    } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function cancelBooking(booking) {
    setBusy(true)
    try { await request(`/bookings/${booking.booking_id}/cancel`, { token, method: 'POST' }); setMessage(`Booking #${booking.booking_id} cancelled.`); await loadBookings() }
    catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  function signOut() { sessionStorage.removeItem('charter_token'); setToken(null); setUser(null); setBookings([]); setResults([]); setActiveView('search'); setMessage('You’ve signed out.') }
  function openTrips() {
    setActiveView('bookings')
    loadBookings()
    window.setTimeout(() => document.getElementById('trips')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }
  function openSearch() {
    setActiveView('search')
    window.setTimeout(() => document.getElementById('search')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }
  const [operatorTab, setOperatorTab] = useState('overview')
  function openOperator(tab = 'overview') { setOperatorTab(tab); setActiveView('operator'); window.setTimeout(() => document.getElementById('operator')?.scrollIntoView({ behavior: 'smooth' }), 50) }

  return <main id="home" className="landing" aria-label="Charter Jet Services">
    <Navbar onTripsClick={openTrips} onOperatorClick={openOperator} onBookClick={user?.role === 'operator' ? () => openOperator('add') : openSearch} onNavigate={() => setActiveView('search')} hasUser={Boolean(user)} hasOperator={user?.role === 'operator'} accountLabel={user ? 'Sign out' : undefined} onAccountClick={signOut} onSignIn={() => { setAuthMode('login'); setAuthOpen(true) }} />
    <div className="landing-art" aria-hidden="true" style={{ transform: `translateX(-${scrollProgress * 100}vw)` }} />
    <div className="landing-blackout" aria-hidden="true" style={{ opacity: scrollProgress }} />
    <GlobeFlight onProgressChange={setScrollProgress}>
      <aside className="promise-strip" aria-label="The Aero Charter promise">
        <div className="promise-heading" style={{ opacity: Math.min(1, Math.max(0, (scrollProgress - 0.42) / 0.12)), transform: `translateX(${Math.max(0, 1 - (scrollProgress - 0.42) / 0.12) * 60}px)` }}>
          <div className="eyebrow"><span/> THE AERO CHARTER PROMISE</div><h2>Travel with<br/><em>confidence.</em></h2>
        </div>
        <div className="promise-rail">
          {[
            ['01', 'Fly on your time', 'Choose a departure that fits your plans, from 30 minutes to a year ahead.'],
            ['02', 'The right aircraft', 'We match your route and passenger count with available aircraft and crew.'],
            ['03', 'Know the fare upfront', 'See your estimated fare before booking, then manage your trip online.'],
          ].map(([number, title, body], index) => {
            const start = 0.48 + index * 0.14
            const reveal = Math.min(1, Math.max(0, (scrollProgress - start) / 0.11))
            return <article className="promise-card" key={number} style={{ opacity: reveal, transform: `translateX(${(1 - reveal) * 88}px)` }}>
              <span className="promise-number">{number}</span><div><h3>{title}</h3><p>{body}</p></div>
            </article>
          })}
        </div>
      </aside>
    </GlobeFlight>
    <div className="api-content">
      {activeView === 'operator' && user?.role === 'operator' ? <OperatorDesk key={operatorTab} initialTab={operatorTab} token={token} locations={locations} dateMin={dateMin} busy={busy} setBusy={setBusy} setMessage={setMessage} message={message} /> : activeView === 'search' ? <>
        <section className={`search-section ${searchDone ? 'has-results' : 'no-results'}`} id="search"><div className="section-intro"><h2>Where to next?</h2></div>
          <form className="search-card" onSubmit={handleSearch}><label className="field"><span><Icon name="pin" size={17}/> Departure airport</span><select value={origin} onChange={(e) => setOrigin(e.target.value)} required><option value="" disabled>Select departure</option>{locations.map((p) => <option key={p.location_id} value={p.location_id}>{p.city} · {p.code}</option>)}</select></label><div className="route-arrow"><Icon name="arrow" size={18}/></div><label className="field"><span><Icon name="pin" size={17}/> Arrival airport</span><select value={destination} onChange={(e) => setDestination(e.target.value)} required><option value="" disabled>Select destination</option>{locations.map((p) => <option key={p.location_id} value={p.location_id}>{p.city} · {p.code}</option>)}</select></label><label className="field"><span><Icon name="calendar" size={17}/> Departure date and time</span><input type="datetime-local" min={dateMin} value={departure} onChange={(e) => setDeparture(e.target.value)} required/></label><label className="field passenger-field"><span><Icon name="user" size={17}/> Number of passengers</span><input type="number" min="1" max={rules.max_passengers} value={passengers} onChange={(e) => setPassengers(e.target.value)} required/></label><button className="search-button" disabled={busy}>{busy ? 'Searching…' : 'Find flights'} <Icon name="arrow" size={18}/></button></form>
          {message && <div className="notice" role="status">{message}<button onClick={() => setMessage('')} aria-label="Dismiss">×</button></div>}
          {searchDone && <div className="results"><div className="results-heading"><div><h3>{results.length ? `${results.length} aircraft ready` : 'No aircraft found'}</h3></div><span className="route-summary">{placeName(origin)?.code} <Icon name="arrow" size={15}/> {placeName(destination)?.code}</span></div>{results.length ? <div className="flight-grid">{results.map((flight) => <article className="flight-card" key={flight.aircraft_id}><div className="flight-card-top"><span className="category-pill">{flight.category}</span><span className="seat-count">{flight.seats} seats</span></div><h4>{flight.model}</h4><div className="flight-route"><span>{placeName(origin)?.city || placeName(origin)?.code}</span><span className="route-line"><i/><Icon name="plane" size={16}/><i/></span><span>{placeName(destination)?.city || placeName(destination)?.code}</span></div><div className="flight-meta"><span>{Number(flight.flight_hours).toFixed(1)} hrs <small>flight time</small></span><span>{Number(flight.distance_nm).toFixed(0)} nm <small>distance</small></span></div><div className="flight-card-bottom"><div><small>ESTIMATED FARE</small><strong>{money(flight.fare)}</strong></div><button onClick={() => bookFlight(flight)} disabled={busy}>Select <Icon name="arrow" size={16}/></button></div></article>)}</div> : <p className="empty-copy">Try another date or route to see more options.</p>}</div>}
        </section>
      </> : <section className="trips-section" id="trips"><div className="trips-heading"><div><h2>Your trips</h2><p>All your upcoming and past charter flights in one place.</p></div><button className="outline-button" onClick={() => { setActiveView('search'); setMessage('') }}>Find a flight <Icon name="arrow" size={16}/></button></div>{message && <div className="notice" role="status">{message}<button onClick={() => setMessage('')}>×</button></div>}{busy && !bookings.length ? <p className="empty-copy">Loading your trips…</p> : bookings.length ? <div className="booking-list">{bookings.map((booking) => <article className="booking-card" key={booking.booking_id}><div className="booking-route"><span>{booking.origin_code}</span><Icon name="arrow" size={18}/><span>{booking.dest_code}</span></div><div><strong>{booking.aircraft_model}</strong><small>{new Date(booking.departure_time).toLocaleString()}</small></div><span className={`status status-${booking.status.toLowerCase()}`}>{booking.status}</span><div className="booking-balance"><small>{booking.balance_due > 0 ? 'BALANCE DUE' : 'TOTAL FARE'}</small><strong>{money(booking.balance_due > 0 ? booking.balance_due : booking.total_fare)}</strong></div><div className="booking-actions">{booking.status === 'Pending' && booking.balance_due > 0 && <><select aria-label="Payment method" value={payments[booking.booking_id] || 'Card'} onChange={(e) => setPayments({ ...payments, [booking.booking_id]: e.target.value })}><option>Card</option><option>UPI</option><option>Bank transfer</option></select><button onClick={() => payBooking(booking)} disabled={busy}>Pay balance</button></>}{['Pending', 'Confirmed'].includes(booking.status) && <button className="cancel-button" onClick={() => cancelBooking(booking)} disabled={busy}>Cancel</button>}</div></article>)}</div> : <div className="empty-state"><div className="empty-icon"><Icon name="plane" size={24}/></div><h3>Your next trip starts here.</h3><p>Search available charter flights and your bookings will appear here.</p><button className="primary-button" onClick={() => setActiveView('search')}>Find a flight <Icon name="arrow" size={16}/></button></div>}</section>}
    </div>

    <footer className="footer"><a className="brand footer-brand" href="#home"><span className="brand-mark"><Icon name="plane" size={17}/></span><span>AERO<span className="brand-light">CHARTER</span></span></a><span>Travel, considered.</span><span>© 2025 Aero Charter</span></footer>

    {authOpen && <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setAuthOpen(false) }}><section className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-title"><button className="modal-close" onClick={() => setAuthOpen(false)} aria-label="Close">×</button>{message && <div className="auth-error auth-error-top" role="alert">{message}</div>}<h2 id="auth-title">{authMode === 'login' ? 'Welcome back.' : accountType === 'operator' ? 'Register as an operator.' : 'Create your account.'}</h2><p>{accountType === 'operator' ? 'Access your aircraft, maintenance, pilots and flights.' : authMode === 'login' ? 'Sign in to explore flights and manage your trips.' : 'A few details and you’ll be ready to fly.'}</p><form onSubmit={handleAuth}><label>Account type<select value={accountType} onChange={(e) => setAccountType(e.target.value)}><option value="customer">Customer</option><option value="operator">Aircraft operator</option></select></label>{authMode === 'register' && <><label>{accountType === 'operator' ? 'Company name' : 'Full name'}<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required maxLength="100"/></label>{accountType === 'operator' && <><label>Operator license number<input value={form.license_no} onChange={(e) => setForm({ ...form, license_no: e.target.value })} required/></label><label>Company city<input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required/></label></>}<label>Phone<input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} required/></label>{accountType === 'customer' ? <label>ID proof<input value={form.id_proof} onChange={(e) => setForm({ ...form, id_proof: e.target.value })} required/></label> : <label>Service interval in flight hours (optional)<input type="number" min="1" max="5000" value={form.service_interval_hrs} onChange={(e) => setForm({ ...form, service_interval_hrs: e.target.value })}/></label>}</>}<label>Email address<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required/></label>{accountType === 'operator' && authMode === 'login' && <label>Operator license number<input value={form.license_no} onChange={(e) => setForm({ ...form, license_no: e.target.value })} required autoComplete="organization-title"/></label>}<label>Password<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={authMode === 'register' ? 10 : 1}/></label>{authMode === 'register' && <small className="password-hint">Use at least 10 characters, including a letter and a number.</small>}<button className="primary-button auth-submit" disabled={busy}>{busy ? 'Please wait…' : authMode === 'login' ? 'Sign in' : 'Create account'} <Icon name="arrow" size={17}/></button></form><div className="auth-switch">{authMode === 'login' ? 'New to Aero Charter?' : 'Already have an account?'} <button onClick={() => { setAuthMode(authMode === 'login' ? 'register' : 'login'); setMessage('') }}>{authMode === 'login' ? 'Create an account' : 'Sign in'}</button></div></section></div>}
  </main>
}

export default App
