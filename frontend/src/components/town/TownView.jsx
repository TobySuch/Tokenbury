import { useState, useEffect, useRef } from 'react'
import { fetchLocations, fetchLatestTick } from '../../api/client'
import AgentSprite from '../agents/AgentSprite'

const FILL_COLOURS = [
  'rgba(239,68,68,0.35)',
  'rgba(34,197,94,0.35)',
  'rgba(59,130,246,0.35)',
  'rgba(234,179,8,0.35)',
  'rgba(168,85,247,0.35)',
  'rgba(249,115,22,0.35)',
  'rgba(20,184,166,0.35)',
  'rgba(236,72,153,0.35)',
  'rgba(6,182,212,0.35)',
  'rgba(132,204,22,0.35)',
  'rgba(99,102,241,0.35)',
  'rgba(244,63,94,0.35)',
  'rgba(245,158,11,0.35)',
  'rgba(217,70,239,0.35)',
  'rgba(14,165,233,0.35)',
  'rgba(16,185,129,0.35)',
  'rgba(220,38,38,0.35)',
  'rgba(22,163,74,0.35)',
  'rgba(37,99,235,0.35)',
  'rgba(202,138,4,0.35)',
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
  'rgb(6,182,212)',
  'rgb(132,204,22)',
  'rgb(99,102,241)',
  'rgb(244,63,94)',
  'rgb(245,158,11)',
  'rgb(217,70,239)',
  'rgb(14,165,233)',
  'rgb(16,185,129)',
  'rgb(220,38,38)',
  'rgb(22,163,74)',
  'rgb(37,99,235)',
  'rgb(202,138,4)',
]

export default function TownView({ onAgentChange }) {
  const isDebug = new URLSearchParams(window.location.search).get('debug') === '1'
  const [locations, setLocations] = useState([])
  const [agentsByLocation, setAgentsByLocation] = useState(new Map())
  const [naturalSize, setNaturalSize] = useState(null)
  const [hoverCoords, setHoverCoords] = useState(null)
  const [hoveredAgent, setHoveredAgent] = useState(null)
  const [lockedAgent, setLockedAgent] = useState(null)
  const lockedAgentRef = useRef(null)
  const imgRef = useRef(null)

  useEffect(() => {
    Promise.all([fetchLocations(), fetchLatestTick()]).then(([locs, tick]) => {
      setLocations(locs)
      if (tick?.agent_states) {
        const byLoc = new Map()
        for (const state of tick.agent_states) {
          if (!state.location_slug) continue
          if (!byLoc.has(state.location_slug)) byLoc.set(state.location_slug, [])
          byLoc.get(state.location_slug).push(state)
        }
        setAgentsByLocation(byLoc)
        if (lockedAgentRef.current) {
          const updated = tick.agent_states.find(
            (s) => s.agent_id === lockedAgentRef.current.agent_id
          )
          if (updated) {
            const locName = locs.find((l) => l.slug === updated.location_slug)?.name
            const enriched = { ...updated, location_name: locName }
            setLockedAgent(enriched)
            lockedAgentRef.current = enriched
            onAgentChange?.(enriched)
          }
        }
      }
    })
  }, [])

  function handleSpriteHover(agent) {
    setHoveredAgent(agent)
    onAgentChange?.(agent)
  }

  function handleSpriteHoverEnd() {
    setHoveredAgent(null)
    onAgentChange?.(lockedAgentRef.current)
  }

  function handleSpriteClick(agent) {
    setLockedAgent(agent)
    lockedAgentRef.current = agent
    onAgentChange?.(agent)
  }

  function handleImageLoad() {
    const img = imgRef.current
    setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight })
  }

  function handleMouseMove(e) {
    if (!naturalSize) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = Math.round(((e.clientX - rect.left) / rect.width) * naturalSize.width)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * naturalSize.height)
    setHoverCoords({ x, y })
  }

  function handleMouseLeave() {
    setHoverCoords(null)
  }

  return (
    <div
      className={`relative w-full overflow-hidden rounded-2xl shadow-md ${isDebug ? 'cursor-crosshair' : ''}`}
      onMouseMove={isDebug ? handleMouseMove : undefined}
      onMouseLeave={isDebug ? handleMouseLeave : undefined}
    >
      <img
        ref={imgRef}
        src="/assets/map/town.png"
        alt="Tokenbury-on-Sea map"
        className="block w-full"
        onLoad={handleImageLoad}
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
              className="absolute box-border"
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
                backgroundColor: fill,
                border: `2px solid ${border}`,
              }}
            >
              <span
                className="pointer-events-none absolute bottom-0.5 left-1 right-1 text-[11px] font-bold"
                style={{ color: border, textShadow: '0 1px 2px rgba(0,0,0,0.85)' }}
              >
                {loc.name}
              </span>
            </div>
          )
        })}
      {naturalSize &&
        locations
          .filter((loc) => agentsByLocation.has(loc.slug))
          .map((loc) => {
            const cx = ((loc.bbox_x1 + loc.bbox_x2) / 2 / naturalSize.width) * 100
            const cy = ((loc.bbox_y1 + loc.bbox_y2) / 2 / naturalSize.height) * 100
            return (
              <div
                key={loc.slug}
                className="absolute flex gap-1 transition-all duration-[2000ms]"
                style={{ left: `${cx}%`, top: `${cy}%`, transform: 'translate(-50%, -50%)' }}
              >
                {agentsByLocation.get(loc.slug).map((a) => (
                  <AgentSprite
                    key={a.agent_id}
                    name={a.agent_name}
                    spriteUrl={a.agent_sprite_url}
                    isActive={a.agent_id === (hoveredAgent?.agent_id ?? lockedAgent?.agent_id)}
                    onHover={() => handleSpriteHover({ ...a, location_name: loc.name })}
                    onHoverEnd={handleSpriteHoverEnd}
                    onClick={() => handleSpriteClick({ ...a, location_name: loc.name })}
                  />
                ))}
              </div>
            )
          })}
      {isDebug && hoverCoords && (
        <div className="pointer-events-none absolute bottom-1.5 right-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-xs text-white">
          {hoverCoords.x}, {hoverCoords.y}
        </div>
      )}
    </div>
  )
}
