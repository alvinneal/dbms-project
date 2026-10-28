import { money } from '../../utils/format'

export default function FlightsTable({ flights }) {
  return (
    <div className="operator-table-wrap">
      <h3>Customer flights</h3>
      <table className="operator-table">
        <thead><tr><th>Route</th><th>Customer</th><th>Aircraft</th><th>Departure</th><th>Status</th><th>Fare due</th></tr></thead>
        <tbody>{flights.map((item) => (
          <tr key={item.booking_id}>
            <td>{item.origin_code} → {item.dest_code}</td><td>{item.customer_name}</td><td>{item.registration_no}</td>
            <td>{new Date(item.departure_time).toLocaleString()}</td><td>{item.status}</td><td>{money(item.balance_due)}</td>
          </tr>
        ))}</tbody>
      </table>
      {!flights.length && <p className="empty-copy">No customer flights booked yet.</p>}
    </div>
  )
}
