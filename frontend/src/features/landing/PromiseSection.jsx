export default function PromiseSection({ progress }) {
  const promisePoints = [
    ['01', 'Fly on your time', 'Choose a departure that fits your plans, from 30 minutes to a year ahead.'],
    ['02', 'The right aircraft', 'We match your route and passenger count with available aircraft and crew.'],
    ['03', 'Know the fare upfront', 'See your estimated fare before booking, then manage your trip online.'],
  ]

  return (
    <aside className="promise-strip" aria-label="The Aero Charter promise">
      <div className="promise-heading" style={{
        opacity: Math.min(1, Math.max(0, (progress - 0.42) / 0.12)),
        transform: `translateX(${Math.max(0, 1 - (progress - 0.42) / 0.12) * 60}px)`,
      }}>
        <div className="eyebrow"><span/> THE AERO CHARTER PROMISE</div>
        <h2>Travel with<br/><em>confidence.</em></h2>
      </div>
      <div className="promise-rail">
        {promisePoints.map(([number, title, body], index) => {
          const start = 0.48 + index * 0.14
          const reveal = Math.min(1, Math.max(0, (progress - start) / 0.11))
          return (
            <article className="promise-card" key={number}
              style={{ opacity: reveal, transform: `translateX(${(1 - reveal) * 88}px)` }}>
              <span className="promise-number">{number}</span>
              <div><h3>{title}</h3><p>{body}</p></div>
            </article>
          )
        })}
      </div>
    </aside>
  )
}
