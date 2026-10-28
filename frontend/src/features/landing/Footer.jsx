import Icon from '../../components/Icon'

export default function Footer() {
  return (
    <footer className="footer">
      <a className="brand footer-brand" href="#home">
        <span className="brand-mark"><Icon name="plane" size={17}/></span>
        <span>AERO<span className="brand-light">CHARTER</span></span>
      </a>
      <span>Travel, considered.</span>
      <span>© 2025 Aero Charter</span>
    </footer>
  )
}
