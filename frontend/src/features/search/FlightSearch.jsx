import Icon from '../../components/Icon'
import Notice from '../../components/Notice'
import { money } from '../../utils/format'

function FlightCard({ flight, origin, destination, onSelect, busy }) {
  return (
    <article className="flight-card">
      <div className="flight-card-top">
        <span className="category-pill">{flight.category}</span>
        <span className="seat-count">{flight.seats} seats</span>
      </div>
      <h4>{flight.model}</h4>
      <div className="flight-route">
        <span>{origin?.city || origin?.code}</span>
        <span className="route-line"><i/><Icon name="plane" size={16}/><i/></span>
        <span>{destination?.city || destination?.code}</span>
      </div>
      <div className="flight-meta">
        <span>{Number(flight.flight_hours).toFixed(1)} hrs <small>flight time</small></span>
        <span>{Number(flight.distance_nm).toFixed(0)} nm <small>distance</small></span>
      </div>
      <div className="flight-card-bottom">
        <div><small>ESTIMATED FARE</small><strong>{money(flight.fare)}</strong></div>
        <button onClick={() => onSelect(flight)} disabled={busy}>Select <Icon name="arrow" size={16}/></button>
      </div>
    </article>
  )
}

export default function FlightSearch({
  locations, origin, destination, departure, passengers, maxPassengers, dateMin,
  results, searchDone, busy, message, onMessageDismiss, onOriginChange,
  onDestinationChange, onDepartureChange, onPassengersChange, onSubmit, onSelectFlight,
}) {
  const originPlace = locations.find((place) => String(place.location_id) === String(origin))
  const destinationPlace = locations.find((place) => String(place.location_id) === String(destination))

  return (
    <section className={`search-section ${searchDone ? 'has-results' : 'no-results'}`} id="search">
      <div className="section-intro"><h2>Where to next?</h2></div>
      <form className="search-card" onSubmit={onSubmit}>
        <label className="field">
          <span><Icon name="pin" size={17}/> Departure airport</span>
          <select value={origin} onChange={(event) => onOriginChange(event.target.value)} required>
            <option value="" disabled>Select departure</option>
            {locations.map((place) => <option key={place.location_id} value={place.location_id}>{place.city} · {place.code}</option>)}
          </select>
        </label>
        <div className="route-arrow"><Icon name="arrow" size={18}/></div>
        <label className="field">
          <span><Icon name="pin" size={17}/> Arrival airport</span>
          <select value={destination} onChange={(event) => onDestinationChange(event.target.value)} required>
            <option value="" disabled>Select destination</option>
            {locations.map((place) => <option key={place.location_id} value={place.location_id}>{place.city} · {place.code}</option>)}
          </select>
        </label>
        <label className="field">
          <span><Icon name="calendar" size={17}/> Departure date and time</span>
          <input type="datetime-local" min={dateMin} value={departure}
            onChange={(event) => onDepartureChange(event.target.value)} required/>
        </label>
        <label className="field passenger-field">
          <span><Icon name="user" size={17}/> Number of passengers</span>
          <input type="number" min="1" max={maxPassengers} value={passengers}
            onChange={(event) => onPassengersChange(event.target.value)} required/>
        </label>
        <button className="search-button" disabled={busy}>
          {busy ? 'Searching…' : 'Find flights'} <Icon name="arrow" size={18}/>
        </button>
      </form>

      <Notice onDismiss={onMessageDismiss}>{message}</Notice>

      {searchDone && (
        <div className="results">
          <div className="results-heading">
            <div><h3>{results.length ? `${results.length} aircraft ready` : 'No aircraft found'}</h3></div>
            <span className="route-summary">{originPlace?.code} <Icon name="arrow" size={15}/> {destinationPlace?.code}</span>
          </div>
          {results.length ? (
            <div className="flight-grid">
              {results.map((flight) => (
                <FlightCard key={flight.aircraft_id} flight={flight} origin={originPlace}
                  destination={destinationPlace} onSelect={onSelectFlight} busy={busy}/>
              ))}
            </div>
          ) : <p className="empty-copy">Try another date or route to see more options.</p>}
        </div>
      )}
    </section>
  )
}
