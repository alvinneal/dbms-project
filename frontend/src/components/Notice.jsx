export default function Notice({ children, onDismiss, role = 'status', className = '' }) {
  if (!children) return null

  return (
    <div className={`notice ${className}`.trim()} role={role}>
      {children}
      <button type="button" onClick={onDismiss} aria-label="Dismiss">×</button>
    </div>
  )
}
