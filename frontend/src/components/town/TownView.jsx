import { useState, useEffect, useRef, useMemo } from 'react'
import AgentSprite from '../agents/AgentSprite'
import TickClock from './TickClock'

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

export default function TownView({
  instance,
  locations = [],
  tickData,
  onAgentChange,
  className = '',
}) {
  const isDebug = new URLSearchParams(window.location.search).get('debug') === '1'
  const [naturalSize, setNaturalSize] = useState(null)
  const [hoverCoords, setHoverCoords] = useState(null)
  const [hoveredAgent, setHoveredAgent] = useState(null)
  const [lockedAgent, setLockedAgent] = useState(null)
  const lockedAgentRef = useRef(null)
  const imgRef = useRef(null)

  // Each agent gets an individual absolutely-positioned wrapper keyed by agent_id.
  // This gives React a stable DOM element to apply CSS transitions to when the
  // agent's location (and therefore left/top) changes between ticks.
  const agentPositions = useMemo(() => {
    if (!tickData?.agent_states || !naturalSize) return []
    const byLoc = new Map()
    for (const state of tickData.agent_states) {
      if (!state.location_slug) continue
      const loc = locations.find((l) => l.slug === state.location_slug)
      if (!loc) continue
      if (!byLoc.has(state.location_slug)) byLoc.set(state.location_slug, [])
      byLoc.get(state.location_slug).push({ state, loc })
    }
    const result = []
    for (const [, agents] of byLoc) {
      agents.sort((a, b) => a.state.agent_id - b.state.agent_id)
      const n = agents.length
      agents.forEach(({ state, loc }, i) => {
        const cx = ((loc.bbox_x1 + loc.bbox_x2) / 2 / naturalSize.width) * 100
        const cy = ((loc.bbox_y1 + loc.bbox_y2) / 2 / naturalSize.height) * 100
        // Spread co-located agents horizontally, centred on the location midpoint
        const offsetPct = (i - (n - 1) / 2) * 3.5
        result.push({ state, loc, cx: cx + offsetPct, cy })
      })
    }
    return result
  }, [tickData, locations, naturalSize])

  useEffect(() => {
    if (!tickData?.agent_states || !lockedAgentRef.current) return
    const updated = tickData.agent_states.find(
      (s) => s.agent_id === lockedAgentRef.current.agent_id
    )
    if (updated) {
      const loc = locations.find((l) => l.slug === updated.location_slug)
      const enriched = enrichAgent(updated, loc ?? { name: null, description: null })
      setLockedAgent(enriched)
      lockedAgentRef.current = enriched
      onAgentChange?.(enriched)
    }
  }, [tickData, locations, onAgentChange])

  function enrichAgent(agent, loc) {
    return {
      ...agent,
      location_name: loc.name,
      location_description: loc.description,
    }
  }

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

  // Limit the map width so its height never pushes content below the fold.
  // --map-height-offset (set in index.css) varies by screen size and orientation:
  // large/portrait uses 20rem (accounts for header + scrubber), landscape small
  // uses 4.5rem (scrubber is hidden, shorter header).
  const mapMaxWidth = naturalSize
    ? `calc((100vh - var(--map-height-offset)) * ${naturalSize.width / naturalSize.height})`
    : undefined

  return (
    <div
      className={`relative mx-auto w-full overflow-hidden rounded-2xl shadow-md ${isDebug ? 'cursor-crosshair' : ''} ${className}`}
      style={mapMaxWidth ? { maxWidth: mapMaxWidth } : undefined}
      onMouseMove={isDebug ? handleMouseMove : undefined}
      onMouseLeave={isDebug ? handleMouseLeave : undefined}
    >
      <TickClock inGameTime={tickData?.in_game_time} />
      {instance?.map_image_url && (
        <img
          ref={imgRef}
          src={instance.map_image_url}
          alt="Tokenbury-on-Sea map"
          className="block w-full"
          onLoad={handleImageLoad}
        />
      )}
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
      {agentPositions.map(({ state, loc, cx, cy }) => (
        <div
          key={state.agent_id}
          className="absolute transition-all duration-[2000ms]"
          style={{ left: `${cx}%`, top: `${cy}%`, transform: 'translate(-50%, -50%)' }}
        >
          <AgentSprite
            name={state.agent_name}
            spriteUrl={state.agent_sprite_url}
            isActive={state.agent_id === (hoveredAgent?.agent_id ?? lockedAgent?.agent_id)}
            onHover={() => handleSpriteHover(enrichAgent(state, loc))}
            onHoverEnd={handleSpriteHoverEnd}
            onClick={() => handleSpriteClick(enrichAgent(state, loc))}
          />
        </div>
      ))}
      {isDebug && hoverCoords && (
        <div className="pointer-events-none absolute bottom-1.5 right-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-xs text-white">
          {hoverCoords.x}, {hoverCoords.y}
        </div>
      )}
    </div>
  )
}
