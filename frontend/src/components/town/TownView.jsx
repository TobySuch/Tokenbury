import { useState, useEffect, useRef } from 'react'
import { fetchLocations } from '../../api/client'

const FILL_COLOURS = [
  'rgba(239,68,68,0.35)',
  'rgba(34,197,94,0.35)',
  'rgba(59,130,246,0.35)',
  'rgba(234,179,8,0.35)',
  'rgba(168,85,247,0.35)',
  'rgba(249,115,22,0.35)',
  'rgba(20,184,166,0.35)',
  'rgba(236,72,153,0.35)',
]

const BORDER_COLOURS = [
  'rgb(239,68,68)',
  'rgb(34,197,94)',
  'rgb(59,130,246)',
  'rgb(234,179,8)',
  'rgb(168,85,247)',
  'rgb(249,115,22)',
  'rgb(20,184,166)',
  'rgb(236,72,153)',
]

export default function TownView() {
  const isDebug = new URLSearchParams(window.location.search).get('debug') === '1'
  const [locations, setLocations] = useState([])
  const [naturalSize, setNaturalSize] = useState(null)
  const [hoverCoords, setHoverCoords] = useState(null)
  const imgRef = useRef(null)

  useEffect(() => {
    fetchLocations().then(setLocations)
  }, [])

  function handleImageLoad() {
    const img = imgRef.current
    setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight })
  }

  function handleMouseMove(e) {
    if (!naturalSize) return
    const rect = imgRef.current.getBoundingClientRect()
    const x = Math.round(((e.clientX - rect.left) / rect.width) * naturalSize.width)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * naturalSize.height)
    setHoverCoords({ x, y })
  }

  function handleMouseLeave() {
    setHoverCoords(null)
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <img
        ref={imgRef}
        src="/assets/map/town.png"
        alt="Tokenbury-on-Sea map"
        style={{ display: 'block', maxWidth: '100%', cursor: isDebug ? 'crosshair' : 'default' }}
        onLoad={handleImageLoad}
        onMouseMove={isDebug ? handleMouseMove : undefined}
        onMouseLeave={isDebug ? handleMouseLeave : undefined}
      />
      {isDebug &&
        naturalSize &&
        locations.map((loc, i) => {
          const fill = FILL_COLOURS[i % FILL_COLOURS.length]
          const border = BORDER_COLOURS[i % BORDER_COLOURS.length]
          const left = (loc.bbox_x1 / naturalSize.width) * 100
          const top = (loc.bbox_y1 / naturalSize.height) * 100
          const width = ((loc.bbox_x2 - loc.bbox_x1) / naturalSize.width) * 100
          const height = ((loc.bbox_y2 - loc.bbox_y1) / naturalSize.height) * 100
          return (
            <div
              key={loc.slug}
              title={loc.name}
              style={{
                position: 'absolute',
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
                backgroundColor: fill,
                border: `2px solid ${border}`,
                boxSizing: 'border-box',
                cursor: 'default',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  bottom: 2,
                  left: 4,
                  fontSize: 11,
                  fontWeight: 700,
                  color: border,
                  textShadow: '0 1px 2px rgba(0,0,0,0.85)',
                  whiteSpace: 'nowrap',
                  pointerEvents: 'none',
                }}
              >
                {loc.name}
              </span>
            </div>
          )
        })}
      {isDebug && hoverCoords && (
        <div
          style={{
            position: 'absolute',
            bottom: 6,
            right: 8,
            background: 'rgba(0,0,0,0.7)',
            color: '#fff',
            fontFamily: 'monospace',
            fontSize: 12,
            padding: '2px 6px',
            borderRadius: 3,
            pointerEvents: 'none',
          }}
        >
          {hoverCoords.x}, {hoverCoords.y}
        </div>
      )}
    </div>
  )
}
