import Icon from '../../components/Icon'
import { bookingReference, money } from '../../utils/format'

function dateTime(value) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export default function BookingReceipt({ booking, onClose }) {
  if (!booking) return null

  const isConfirmed = booking.status === 'Confirmed'
  const title = isConfirmed
    ? 'Boarding pass'
    : booking.status === 'Cancelled' ? 'Cancelled booking receipt' : 'Booking receipt'

  return (
    <div className="receipt-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="booking-receipt" role="dialog" aria-modal="true" aria-labelledby="receipt-title">
        <div className="receipt-actions no-print">
          <button className="receipt-print-button" onClick={() => window.print()}>Print / Save PDF</button>
          <button className="modal-close" onClick={onClose} aria-label="Close receipt">×</button>
        </div>

        <header className="receipt-header">
          <div className="receipt-brand"><span className="brand-mark"><Icon name="plane" size={17}/></span>AERO<span>CHARTER</span></div>
          <span className={`receipt-status status-${booking.status.toLowerCase()}`}>{booking.status}</span>
        </header>

        <div className="receipt-title-row">
          <div><p className="receipt-kicker">FLIGHT DOCUMENT</p><h2 id="receipt-title">{title}</h2></div>
          <div className="receipt-reference"><small>BOOKING REFERENCE</small><strong>{bookingReference(booking.booking_id, booking.departure_time)}</strong></div>
        </div>

        {booking.status === 'Pending' && (
          <p className="receipt-notice">Payment is still due. Your booking will be confirmed once the balance is paid.</p>
        )}
        {booking.status === 'Cancelled' && (
          <p className="receipt-notice">This booking has been cancelled. Keep this receipt for your records.</p>
        )}

        <div className="receipt-route">
          <div><small>FROM</small><strong>{booking.origin_code}</strong><span>{dateTime(booking.departure_time)}</span></div>
          <div className="receipt-route-line"><i/><Icon name="plane" size={20}/><i/></div>
          <div><small>TO</small><strong>{booking.dest_code}</strong><span>{dateTime(booking.arrival_time)}</span></div>
        </div>

        <div className="receipt-details">
          <div><small>PASSENGER</small><strong>{booking.customer_name}</strong></div>
          <div><small>AIRCRAFT</small><strong>{booking.aircraft_model}</strong></div>
          <div><small>REGISTRATION</small><strong>{booking.registration_no}</strong></div>
          <div><small>PASSENGERS</small><strong>{booking.passengers}</strong></div>
        </div>

        <div className="receipt-fare">
          <div><span>Total fare</span><strong>{money(booking.total_fare)}</strong></div>
          <div><span>Paid</span><strong>{money(booking.amount_paid)}</strong></div>
          <div className="receipt-balance"><span>Balance due</span><strong>{money(booking.balance_due)}</strong></div>
        </div>

        <footer className="receipt-footer">
          <span>{bookingReference(booking.booking_id, booking.departure_time)}</span>
          <span>Keep this document with your trip details.</span>
        </footer>
      </section>
    </div>
  )
}
