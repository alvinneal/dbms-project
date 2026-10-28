import { useEffect, useMemo, useState } from 'react'
import { request } from './api/client'
import GlobeFlight from './GlobeFlight'
import Navbar from './Navbar'
import AuthModal from './features/auth/AuthModal'
import Footer from './features/landing/Footer'
import PromiseSection from './features/landing/PromiseSection'
import OperatorDesk from './features/operator/OperatorDesk'
import FlightSearch from './features/search/FlightSearch'
import BookingReceipt from './features/trips/BookingReceipt'
import TripsSection from './features/trips/TripsSection'
import { bookingReference, localDateTime } from './utils/format'
import './App.css'

const emptyForm = {
  email: '', password: '', name: '', phone: '', id_proof: '',
  license_no: '', city: '', service_interval_hrs: '',
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
  const [form, setForm] = useState(emptyForm)
  const [accountType, setAccountType] = useState('customer')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [searchDone, setSearchDone] = useState(false)
  const [selectedReceipt, setSelectedReceipt] = useState(null)
  const [receiptOpen, setReceiptOpen] = useState(false)
  const [operatorTab, setOperatorTab] = useState('overview')

  useEffect(() => {
    Promise.all([request('/locations?limit=500'), request('/meta')])
      .then(([places, meta]) => {
        setLocations(places)
        setRules(meta.booking_rules)
        if (places.length > 1) {
          setOrigin(String(places[0].location_id))
          setDestination(String(places[1].location_id))
        }
      })
      .catch((error) => setMessage(error.message))
  }, [])

  useEffect(() => {
    if (!token) {
      setUser(null)
      return
    }

    request('/auth/me', { token })
      .then((current) => {
        setUser(current)
        if (current.role === 'operator') setActiveView('operator')
      })
      .catch(() => {
        sessionStorage.removeItem('charter_token')
        setToken(null)
      })
  }, [token])

  const dateMin = useMemo(
    () => localDateTime(new Date(Date.now() + rules.min_lead_minutes * 60000)),
    [rules.min_lead_minutes],
  )

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function handleSearch(event) {
    event.preventDefault()
    setMessage('')
    if (!token) {
      setAuthOpen(true)
      setMessage('Sign in to see available aircraft and fares.')
      return
    }
    if (!origin || !destination || origin === destination) {
      setMessage('Choose two different destinations.')
      return
    }

    setBusy(true)
    setResults([])
    setSearchDone(false)
    try {
      const params = new URLSearchParams({
        origin_id: origin,
        dest_id: destination,
        departure_time: departure,
        passengers,
      })
      setResults(await request(`/search?${params}`, { token }))
      setSearchDone(true)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleAuth(event) {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      const isOperator = accountType === 'operator'
      const payload = authMode === 'login'
        ? { email: form.email, password: form.password, ...(isOperator ? { license_no: form.license_no } : {}) }
        : isOperator
          ? {
            name: form.name,
            license_no: form.license_no,
            email: form.email,
            password: form.password,
            phone: form.phone,
            city: form.city,
            ...(form.service_interval_hrs ? { service_interval_hrs: Number(form.service_interval_hrs) } : {}),
          }
          : { name: form.name, email: form.email, password: form.password, phone: form.phone, id_proof: form.id_proof }
      const endpoint = isOperator
        ? `/auth/operator/${authMode === 'login' ? 'login' : 'register'}`
        : `/auth/${authMode === 'login' ? 'login' : 'register'}`
      const data = await request(endpoint, { method: 'POST', body: JSON.stringify(payload) })

      sessionStorage.setItem('charter_token', data.access_token)
      setToken(data.access_token)
      setUser(data.user)
      setAuthOpen(false)
      setActiveView(data.user.role === 'operator' ? 'operator' : 'search')
      setMessage(data.user.role === 'operator'
        ? 'Welcome to your operator desk.'
        : 'You’re signed in. Search available flights to get started.')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function bookFlight(flight) {
    if (!user) {
      setAuthOpen(true)
      return
    }
    setBusy(true)
    setMessage('')
    try {
      const booking = await request('/bookings', {
        token,
        method: 'POST',
        body: JSON.stringify({
          aircraft_id: flight.aircraft_id,
          origin_id: Number(origin),
          dest_id: Number(destination),
          departure_time: departure,
          passengers: Number(passengers),
        }),
      })
      setSelectedReceipt(booking)
      await loadBookings()
      setActiveView('bookings')
      setMessage(`Flight reserved. Reference ${bookingReference(booking.booking_id, booking.departure_time)} is pending payment.`)
      setReceiptOpen(true)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function loadBookings() {
    if (!token) {
      setAuthOpen(true)
      return
    }
    setBusy(true)
    try {
      setBookings(await request('/bookings?limit=100', { token }))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function payBooking(booking) {
    setBusy(true)
    setMessage('')
    try {
      await request(`/bookings/${booking.booking_id}/payments`, {
        token,
        method: 'POST',
        body: JSON.stringify({
          amount: Number(booking.balance_due),
          method: payments[booking.booking_id] || 'Card',
        }),
      })
      setMessage(`Payment recorded for ${bookingReference(booking.booking_id, booking.departure_time)}.`)
      await loadBookings()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function cancelBooking(booking) {
    setBusy(true)
    try {
      await request(`/bookings/${booking.booking_id}/cancel`, { token, method: 'POST' })
      setMessage(`${bookingReference(booking.booking_id, booking.departure_time)} cancelled.`)
      await loadBookings()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  function signOut() {
    sessionStorage.removeItem('charter_token')
    setToken(null)
    setUser(null)
    setBookings([])
    setResults([])
    setActiveView('search')
    setMessage('You’ve signed out.')
  }

  function openTrips() {
    setActiveView('bookings')
    loadBookings()
    window.setTimeout(() => document.getElementById('trips')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  function openSearch() {
    setActiveView('search')
    window.setTimeout(() => document.getElementById('search')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  function openOperator(tab = 'overview') {
    setOperatorTab(tab)
    setActiveView('operator')
    window.setTimeout(() => document.getElementById('operator')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  return (
    <main id="home" className="landing" aria-label="Charter Jet Services">
      <Navbar
        onTripsClick={openTrips}
        onOperatorClick={openOperator}
        onBookClick={user?.role === 'operator' ? () => openOperator('add') : openSearch}
        onNavigate={() => setActiveView('search')}
        hasUser={Boolean(user)}
        hasOperator={user?.role === 'operator'}
        accountLabel={user ? 'Sign out' : undefined}
        onAccountClick={signOut}
        onSignIn={() => { setAuthMode('login'); setAuthOpen(true) }}
      />

      <div className="landing-art" aria-hidden="true" style={{ transform: `translateX(-${scrollProgress * 100}vw)` }}/>
      <div className="landing-blackout" aria-hidden="true" style={{ opacity: scrollProgress }}/>
      <GlobeFlight onProgressChange={setScrollProgress}>
        <PromiseSection progress={scrollProgress}/>
      </GlobeFlight>

      <div className="api-content">
        {activeView === 'operator' && user?.role === 'operator' ? (
          <OperatorDesk key={operatorTab} initialTab={operatorTab} token={token} busy={busy}
            setMessage={setMessage} message={message}/>
        ) : activeView === 'search' ? (
          <FlightSearch
            locations={locations}
            origin={origin}
            destination={destination}
            departure={departure}
            passengers={passengers}
            maxPassengers={rules.max_passengers}
            dateMin={dateMin}
            results={results}
            searchDone={searchDone}
            busy={busy}
            message={message}
            onMessageDismiss={() => setMessage('')}
            onOriginChange={setOrigin}
            onDestinationChange={setDestination}
            onDepartureChange={setDeparture}
            onPassengersChange={setPassengers}
            onSubmit={handleSearch}
            onSelectFlight={bookFlight}
          />
        ) : (
          <TripsSection
            bookings={bookings}
            payments={payments}
            busy={busy}
            message={message}
            onMessageDismiss={() => setMessage('')}
            onPaymentMethodChange={(bookingId, method) => setPayments((current) => ({ ...current, [bookingId]: method }))}
            onPay={payBooking}
            onCancel={cancelBooking}
            onViewReceipt={(booking) => { setSelectedReceipt(booking); setReceiptOpen(true) }}
            onFindFlight={() => { setActiveView('search'); setMessage('') }}
          />
        )}
      </div>

      <Footer/>

      {authOpen && (
        <AuthModal
          mode={authMode}
          accountType={accountType}
          form={form}
          busy={busy}
          message={message}
          onClose={() => setAuthOpen(false)}
          onSubmit={handleAuth}
          onFormChange={updateForm}
          onAccountTypeChange={setAccountType}
          onModeChange={() => {
            setAuthMode((current) => current === 'login' ? 'register' : 'login')
            setMessage('')
          }}
        />
      )}
      {receiptOpen && selectedReceipt && (
        <BookingReceipt booking={selectedReceipt} onClose={() => setReceiptOpen(false)}/>
      )}
    </main>
  )
}

export default App
