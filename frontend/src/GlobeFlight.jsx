import { useEffect, useRef, useState } from 'react'
import './GlobeFlight.css'

export default function GlobeFlight({ onProgressChange, children }) {
  const sectionRef = useRef(null)
  const [progress, setProgress] = useState(0)
  const [viewport, setViewport] = useState({ width: window.innerWidth, height: window.innerHeight })

  useEffect(() => {
    const updateProgress = () => {
      const section = sectionRef.current
      if (!section) return

      const travelDistance = section.offsetHeight - window.innerHeight
      const travelled = -section.getBoundingClientRect().top
      const nextProgress = Math.max(0, Math.min(1, travelled / Math.max(1, travelDistance)))
      setProgress(nextProgress)
      onProgressChange?.(nextProgress)
      setViewport({ width: window.innerWidth, height: window.innerHeight })
    }

    updateProgress()
    window.addEventListener('scroll', updateProgress, { passive: true })
    window.addEventListener('resize', updateProgress)
    return () => {
      window.removeEventListener('scroll', updateProgress)
      window.removeEventListener('resize', updateProgress)
    }
  }, [onProgressChange])

  const angle = Math.PI + progress * Math.PI * 2.5
  const cx = 300
  const cy = 205
  const globeRadius = 112
  const viewTilt = (65 * Math.PI / 180) * progress
  const orbitX = 205 - 60 * progress
  const orbitY = 78 + 32 * progress
  const orbitCenterY = cy - 85 * progress
  const orbitRotation = Math.PI / 6
  const orbitCos = Math.cos(orbitRotation)
  const orbitSin = Math.sin(orbitRotation)
  const localX = orbitX * Math.cos(angle)
  const localY = orbitY * Math.sin(angle)
  const x = cx + localX * orbitCos - localY * orbitSin
  const y = orbitCenterY + localX * orbitSin + localY * orbitCos
  const tangentX = -orbitX * Math.sin(angle) * orbitCos - orbitY * Math.cos(angle) * orbitSin
  const tangentY = -orbitX * Math.sin(angle) * orbitSin + orbitY * Math.cos(angle) * orbitCos
  // The plane artwork points upward, so rotate it to match the orbit tangent.
  const rotation = (Math.atan2(tangentX, -tangentY) * 180) / Math.PI
  const startDiameter = viewport.width <= 700
    ? viewport.width * 0.52
    : Math.min(viewport.height * 0.52, viewport.width * 0.3)
  const startSize = startDiameter * (600 / 224)
  const endSize = viewport.height * (600 / 260)
  const svgSize = startSize + (endSize - startSize) * progress
  const startCenterX = viewport.width * 0.74
  const centerX = startCenterX + (viewport.width * 0.5 - startCenterX) * progress
  const centerY = viewport.height * (0.54 + 0.5933 * progress)
  const planeOnTop = Math.sin(angle) >= 0
  const projectPoint = (latitude, longitude) => {
    const latitudeRadius = Math.cos(latitude)
    const worldY = Math.sin(latitude)
    const worldZ = latitudeRadius * Math.cos(longitude)
    const facing = worldY * Math.sin(viewTilt) + worldZ * Math.cos(viewTilt)
    const screenY = worldY * Math.cos(viewTilt) - worldZ * Math.sin(viewTilt)

    return {
      x: cx + globeRadius * latitudeRadius * Math.sin(longitude),
      y: cy - globeRadius * screenY,
      visible: facing >= -0.01,
    }
  }
  const toVisiblePath = (points) => {
    let path = ''
    let segmentOpen = false

    for (const point of points) {
      if (point.visible) {
        path += `${segmentOpen ? 'L' : 'M'}${point.x.toFixed(2)} ${point.y.toFixed(2)} `
        segmentOpen = true
      } else {
        segmentOpen = false
      }
    }

    return path.trim()
  }
  const gridLines = [
    ...[-60, -40, -20, 0, 20, 40, 60].map((degrees) => {
      const latitude = (degrees * Math.PI) / 180
      const points = Array.from({ length: 97 }, (_, index) =>
        projectPoint(latitude, (index / 96) * Math.PI * 2)
      )
      return toVisiblePath(points)
    }),
    ...Array.from({ length: 12 }, (_, index) => {
      const longitude = (index * Math.PI) / 6 + progress * Math.PI * 2
      const points = Array.from({ length: 65 }, (_, pointIndex) => {
        const latitude = -Math.PI / 2 + (pointIndex / 64) * Math.PI
        return projectPoint(latitude, longitude)
      })
      return toVisiblePath(points)
    }),
  ]
  const plane = (
    <g transform={`translate(${x} ${y}) rotate(${rotation})`}>
      <path
        d="M0-18 2.4-5 13.5 2 13.5 4.2 3.5 2 2.5 12 6.5 15.2 6.5 17 0 15.1-6.5 17-6.5 15.2-2.5 12-3.5 2-13.5 4.2-13.5 2-2.4-5Z"
        fill="#fff"
        stroke="#16204f"
        strokeWidth=".7"
        strokeLinejoin="round"
      />
    </g>
  )
  return (
    <section className="gf-section" ref={sectionRef} aria-label="Scroll animated flight around a globe">
      <div className="gf-sticky">
        {children}
        <svg
          className="gf-svg"
          viewBox="0 0 600 410"
          role="img"
          aria-label="A plane circling a spinning globe"
          style={{ width: `${svgSize}px`, left: `${centerX}px`, top: `${centerY}px` }}
        >
          <defs>
            <clipPath id="gf-orbit-front-half">
              <rect x="0" y={orbitCenterY} width="600" height="205" transform={`rotate(30 ${cx} ${orbitCenterY})`} />
            </clipPath>
            <clipPath id="gf-earth-clip">
              <circle cx={cx} cy={cy} r="112" />
            </clipPath>
          </defs>
          <ellipse cx={cx} cy={orbitCenterY} rx={orbitX} ry={orbitY} transform={`rotate(30 ${cx} ${orbitCenterY})`} fill="none" stroke="#666" strokeWidth="3" strokeDasharray="5 6" strokeLinecap="round" opacity=".9" />
          <ellipse cx={cx} cy={orbitCenterY} rx={orbitX} ry={orbitY} transform={`rotate(30 ${cx} ${orbitCenterY})`} fill="none" stroke="#fff" strokeWidth="1.5" strokeDasharray="5 6" strokeLinecap="round" />
          {!planeOnTop && plane}
          <g transform={`rotate(30 ${cx} ${cy})`}>
            <circle cx={cx} cy={cy} r="112" fill="#1C2BFD" />
            <g clipPath="url(#gf-earth-clip)" fill="none" stroke="#fff" strokeWidth="1.5" opacity=".62">
              {gridLines.map((path, index) => (
                <path key={index} d={path} />
              ))}
            </g>
          </g>
          <ellipse cx={cx} cy={orbitCenterY} rx={orbitX} ry={orbitY} transform={`rotate(30 ${cx} ${orbitCenterY})`} fill="none" stroke="#666" strokeWidth="3" strokeDasharray="5 6" strokeLinecap="round" opacity=".9" clipPath="url(#gf-orbit-front-half)" />
          <ellipse cx={cx} cy={orbitCenterY} rx={orbitX} ry={orbitY} transform={`rotate(30 ${cx} ${orbitCenterY})`} fill="none" stroke="#fff" strokeWidth="1.5" strokeDasharray="5 6" strokeLinecap="round" clipPath="url(#gf-orbit-front-half)" />
          {planeOnTop && plane}
        </svg>
      </div>
    </section>
  )
}
