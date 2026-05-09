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
  const [locations, setLocations] = useState([])
  const [naturalSize, setNaturalSize] = useState(null)
  const imgRef = useRef(null)

  useEffect(() => {
    fetchLocations().then(setLocations)
  }, [])

  function handleImageLoad() {
    const img = imgRef.current
    setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight })
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <img
        ref={imgRef}
        src="/assets/map/town.png"
        alt="Tokenbury-on-Sea map"
        style={{ display: 'block', maxWidth: '100%' }}
        onLoad={handleImageLoad}
      />
      {naturalSize &&
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
    </div>
  )
}
