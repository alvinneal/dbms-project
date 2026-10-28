export default function PilotsTable({ pilots }) {
  return (
    <div className="operator-table-wrap">
      <h3>Your pilots</h3>
      <table className="operator-table">
        <thead><tr><th>Name</th><th>License</th><th>Rating</th><th>Experience</th><th>Status</th></tr></thead>
        <tbody>{pilots.map((pilot) => (
          <tr key={pilot.pilot_id}>
            <td>{pilot.name}</td><td>{pilot.license_no}</td><td>{pilot.category_rating}</td>
            <td>{pilot.experience_hours} hrs</td><td>{pilot.status}</td>
          </tr>
        ))}</tbody>
      </table>
      {!pilots.length && <p className="empty-copy">No pilots are assigned to this operator yet.</p>}
    </div>
  )
}
