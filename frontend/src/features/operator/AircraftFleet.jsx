export default function AircraftFleet({ aircraft }) {
  return (
    <div className="operator-table-wrap">
      <h3>Aircraft fleet</h3>
      <table className="operator-table">
        <thead><tr><th>Registration</th><th>Aircraft</th><th>Seats</th><th>Status</th><th>Hours to service</th></tr></thead>
        <tbody>{aircraft.map((item) => (
          <tr key={item.aircraft_id}>
            <td>{item.registration_no}</td><td>{item.type_model}</td><td>{item.seats}</td>
            <td><span className={`status ${item.status === 'Available' ? 'status-confirmed' : ''}`}>{item.status}</span></td>
            <td>{Number(item.service_due_in_hours).toFixed(1)}</td>
          </tr>
        ))}</tbody>
      </table>
      {!aircraft.length && <p className="empty-copy">No aircraft are assigned to this operator yet.</p>}
    </div>
  )
}
