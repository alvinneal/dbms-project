import { useState } from 'react'
import './Navbar.css'

const customerLinks = [
  { label: 'Home', href: '#home' },
  { label: 'Find a Flight', href: '#search' },
  { label: 'My Trips', href: '#trips' },
]

function MenuIcon({ close = false }) {
  return close ? (
    <svg width="25" height="25" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m18 6-12 12M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
  ) : (
    <svg width="25" height="25" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
  )
}

function ArrowIcon() {
  return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

export default function Navbar({ onTripsClick, onOperatorClick, onBookClick, onNavigate, hasUser,
  hasOperator, onAccountClick, accountLabel, onSignIn }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const navLinks = hasOperator
    ? [{ label: 'Operator desk', href: '#operator' }]
    : customerLinks

  return (
    <header className="cj-navbar">
      <button
        className="cj-menu-toggle"
        aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
        aria-expanded={menuOpen}
        aria-controls="cj-navigation"
        onClick={() => setMenuOpen(!menuOpen)}
      >
        <MenuIcon close={menuOpen} />
      </button>

      <nav id="cj-navigation" className={`cj-nav ${menuOpen ? 'is-open' : ''}`}>
        {navLinks.map((link) => (
          link.href === '#trips' ? <button key={link.label} type="button" className="cj-nav-link" onClick={() => { setMenuOpen(false); onTripsClick?.() }}>
            {link.label}
          </button> : link.href === '#operator' ? <button key={link.label} type="button" className="cj-nav-link" onClick={() => { setMenuOpen(false); onOperatorClick?.('overview') }}>
            {link.label}
          </button> :
          <a key={link.label} href={link.href} className="cj-nav-link" onClick={() => { setMenuOpen(false); onNavigate?.(link.href) }}>
            {link.label}
          </a>
        ))}
        <div className="cj-nav-actions">
          <button className="cj-account-button" onClick={hasUser ? onAccountClick : onSignIn}>{accountLabel || (hasUser ? 'My account' : 'Sign in')}</button>
        </div>
      </nav>
    </header>
  )
}
