import Icon from '../../components/Icon'

export default function AddAircraftForm({ aircraftTypes, aircraft, saving, busy, onSubmit, onChange }) {
  return (
    <form className="operator-flight-form" onSubmit={onSubmit}>
      <h3>Add an aircraft</h3>
      <p>Add an aircraft to your fleet by entering its registration and aircraft type.</p>
      <div className="operator-form-grid">
        <label>
          Registration number
          <input required maxLength="15" value={aircraft.registration_no}
            onChange={(event) => onChange({ ...aircraft, registration_no: event.target.value.toUpperCase() })}
            placeholder="VT-ABC"/>
        </label>
        <label>
          Aircraft type
          <select required value={aircraft.type_id}
            onChange={(event) => onChange({ ...aircraft, type_id: event.target.value })}>
            <option value="">Choose aircraft type</option>
            {aircraftTypes.map((type) => (
              <option key={type.type_id} value={type.type_id}>{type.model} · {type.category} ({type.seats} seats)</option>
            ))}
          </select>
        </label>
      </div>
      <button className="primary-button" disabled={saving || busy}>
        {saving ? 'Adding aircraft…' : 'Add aircraft'} <Icon name="arrow" size={17}/>
      </button>
    </form>
  )
}
