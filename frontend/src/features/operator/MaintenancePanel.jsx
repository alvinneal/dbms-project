export default function MaintenancePanel({ aircraft, serviceCosts, saving, onCostChange, onService }) {
  return (
    <div className="operator-table-wrap">
      <h3>Maintenance due</h3>
      <p className="operator-subcopy">Aircraft appear here when marked for maintenance or within 10% of their service interval.</p>
      {aircraft.length ? (
        <div className="maintenance-list">
          {aircraft.map((item) => (
            <article key={item.aircraft_id}>
              <div>
                <b>{item.registration_no} · {item.type_model}</b>
                <small>{Number(item.hours_since_service).toFixed(1)} hours since last service · {item.status}</small>
              </div>
              <label>
                Cost
                <input aria-label={`Service cost for ${item.registration_no}`} type="number" min="0" step="0.01"
                  value={serviceCosts[item.aircraft_id] || ''}
                  onChange={(event) => onCostChange(item.aircraft_id, event.target.value)} placeholder="0.00"/>
              </label>
              <button disabled={saving} onClick={() => onService(item)}>Record service</button>
            </article>
          ))}
        </div>
      ) : <p className="empty-copy">No aircraft currently need maintenance.</p>}
    </div>
  )
}
