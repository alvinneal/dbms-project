export const money = (value) => new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
}).format(value || 0)

export const localDateTime = (date) => (
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  + `T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
)

export const bookingReference = (bookingId, departureTime) => {
  const year = new Date(departureTime).getFullYear()
  return `AC-${year}-${String(bookingId).padStart(6, '0')}`
}
