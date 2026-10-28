import Icon from '../../components/Icon'
import Notice from '../../components/Notice'
import { money } from '../../utils/format'

function BookingCard({ booking, paymentMethod, busy, onPaymentMethodChange, onPay, onCancel, onViewReceipt }) {
  return (
    <article className="booking-card">
      <div className="booking-route"><span>{booking.origin_code}</span><Icon name="arrow" size={18}/><span>{booking.dest_code}</span></div>
      <div><strong>{booking.aircraft_model}</strong><small>{new Date(booking.departure_time).toLocaleString()}</small></div>
      <span className={`status status-${booking.status.toLowerCase()}`}>{booking.status}</span>
      <div className="booking-balance">
        <small>{booking.balance_due > 0 ? 'BALANCE DUE' : 'TOTAL FARE'}</small>
        <strong>{money(booking.balance_due > 0 ? booking.balance_due : booking.total_fare)}</strong>
      </div>
      <div className="booking-actions">
        {/* Keep payment, cancel, and receipt/pass slots fixed; leave unavailable actions empty. */}
        <div className="booking-action-slot booking-payment-slot">
          {booking.status === 'Pending' && booking.balance_due > 0 && (
            <div className="booking-payment-controls">
              <select aria-label="Payment method" value={paymentMethod}
                onChange={(event) => onPaymentMethodChange(event.target.value)}>
                <option>Card</option><option>UPI</option><option>Bank transfer</option>
              </select>
              <button onClick={() => onPay(booking)} disabled={busy}>Pay balance</button>
            </div>
          )}
        </div>
        <div className="booking-action-slot booking-cancel-slot">
          {['Pending', 'Confirmed'].includes(booking.status) && (
            <button className="cancel-button" onClick={() => onCancel(booking)} disabled={busy}>Cancel</button>
          )}
        </div>
        <div className="booking-action-slot booking-receipt-slot">
          <button className="receipt-link" onClick={() => onViewReceipt(booking)}>
            {booking.status === 'Confirmed' ? 'View boarding pass' : 'View receipt'}
          </button>
        </div>
      </div>
    </article>
  )
}

export default function TripsSection({
  bookings, payments, busy, message, onMessageDismiss, onPaymentMethodChange,
  onPay, onCancel, onFindFlight, onViewReceipt,
}) {
  return (
    <section className="trips-section" id="trips">
      <div className="trips-heading">
        <div><h2>Your trips</h2><p>All your upcoming and past charter flights in one place.</p></div>
        <button className="outline-button" onClick={onFindFlight}>Find a flight <Icon name="arrow" size={16}/></button>
      </div>
      <Notice onDismiss={onMessageDismiss}>{message}</Notice>
      {busy && !bookings.length ? <p className="empty-copy">Loading your trips…</p> : bookings.length ? (
        <div className="booking-list">
          {bookings.map((booking) => (
            <BookingCard key={booking.booking_id} booking={booking}
              paymentMethod={payments[booking.booking_id] || 'Card'} busy={busy}
              onPaymentMethodChange={(method) => onPaymentMethodChange(booking.booking_id, method)}
              onPay={onPay} onCancel={onCancel} onViewReceipt={onViewReceipt}/>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon"><Icon name="plane" size={24}/></div>
          <h3>Your next trip starts here.</h3>
          <p>Search available charter flights and your bookings will appear here.</p>
          <button className="primary-button" onClick={onFindFlight}>Find a flight <Icon name="arrow" size={16}/></button>
        </div>
      )}
    </section>
  )
}
