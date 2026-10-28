export default function OperatorOverview({ aircraft, maintenance, pilots, flights, onSelectTab }) {
  return (
    <>
      <div className="operator-stats">
        <button onClick={() => onSelectTab('fleet')}><strong>{aircraft.length}</strong><span>Aircraft in fleet</span></button>
        <button onClick={() => onSelectTab('maintenance')}><strong>{maintenance.length}</strong><span>Need maintenance</span></button>
        <button onClick={() => onSelectTab('pilots')}><strong>{pilots.length}</strong><span>Pilots</span></button>
        <button onClick={() => onSelectTab('flights')}><strong>{flights.length}</strong><span>Booked flights</span></button>
      </div>
      <div className="operator-panels">
        <article>
          <div className="operator-panel-title"><h3>Maintenance attention</h3><button onClick={() => onSelectTab('maintenance')}>View all →</button></div>
          {maintenance.length ? maintenance.slice(0, 3).map((item) => (
            <p className="operator-summary-row" key={item.aircraft_id}>
              <b>{item.registration_no}</b><span>{item.hours_since_service} hours since service</span>
            </p>
          )) : <p className="empty-copy">All aircraft are within their service interval.</p>}
        </article>
        <article>
          <div className="operator-panel-title"><h3>Fleet snapshot</h3><button onClick={() => onSelectTab('fleet')}>View fleet →</button></div>
          {aircraft.slice(0, 3).map((item) => (
            <p className="operator-summary-row" key={item.aircraft_id}>
              <b>{item.registration_no}</b><span>{item.type_model} · {item.status}</span>
            </p>
          ))}
        </article>
      </div>
    </>
  )
}
