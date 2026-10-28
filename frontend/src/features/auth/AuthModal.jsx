import Icon from '../../components/Icon'

export default function AuthModal({
  mode, accountType, form, busy, message, onClose, onSubmit, onFormChange,
  onAccountTypeChange, onModeChange,
}) {
  return (
    <div className="modal-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        {message && <div className="auth-error auth-error-top" role="alert">{message}</div>}
        <h2 id="auth-title">
          {mode === 'login' ? 'Welcome back.' : accountType === 'operator' ? 'Register as an operator.' : 'Create your account.'}
        </h2>
        <p>{accountType === 'operator'
          ? 'Access your aircraft, maintenance, pilots and flights.'
          : mode === 'login' ? 'Sign in to explore flights and manage your trips.' : 'A few details and you’ll be ready to fly.'}</p>

        <form onSubmit={onSubmit}>
          <label>Account type
            <select value={accountType} onChange={(event) => onAccountTypeChange(event.target.value)}>
              <option value="customer">Customer</option><option value="operator">Aircraft operator</option>
            </select>
          </label>
          {mode === 'register' && (
            <>
              <label>{accountType === 'operator' ? 'Company name' : 'Full name'}
                <input value={form.name} onChange={(event) => onFormChange('name', event.target.value)} required maxLength="100"/>
              </label>
              {accountType === 'operator' && (
                <>
                  <label>Operator license number
                    <input value={form.license_no} onChange={(event) => onFormChange('license_no', event.target.value)} required/>
                  </label>
                  <label>Company city
                    <input value={form.city} onChange={(event) => onFormChange('city', event.target.value)} required/>
                  </label>
                </>
              )}
              <label>Phone
                <input value={form.phone} onChange={(event) => onFormChange('phone', event.target.value)} required/>
              </label>
              {accountType === 'customer' ? (
                <label>ID proof
                  <input value={form.id_proof} onChange={(event) => onFormChange('id_proof', event.target.value)} required/>
                </label>
              ) : (
                <label>Service interval in flight hours (optional)
                  <input type="number" min="1" max="5000" value={form.service_interval_hrs}
                    onChange={(event) => onFormChange('service_interval_hrs', event.target.value)}/>
                </label>
              )}
            </>
          )}
          <label>Email address
            <input type="email" value={form.email} onChange={(event) => onFormChange('email', event.target.value)} required/>
          </label>
          {accountType === 'operator' && mode === 'login' && (
            <label>Operator license number
              <input value={form.license_no} onChange={(event) => onFormChange('license_no', event.target.value)} required autoComplete="organization-title"/>
            </label>
          )}
          <label>Password
            <input type="password" value={form.password} onChange={(event) => onFormChange('password', event.target.value)}
              required minLength={mode === 'register' ? 10 : 1}/>
          </label>
          {mode === 'register' && <small className="password-hint">Use at least 10 characters, including a letter and a number.</small>}
          <button className="primary-button auth-submit" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'} <Icon name="arrow" size={17}/>
          </button>
        </form>

        <div className="auth-switch">
          {mode === 'login' ? 'New to Aero Charter?' : 'Already have an account?'}
          <button onClick={onModeChange}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button>
        </div>
      </section>
    </div>
  )
}
