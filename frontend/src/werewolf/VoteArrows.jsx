const TRIM = 9

function shorten(from, to) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  const ux = dx / len
  const uy = dy / len
  return {
    x1: from.x + ux * TRIM,
    y1: from.y + uy * TRIM,
    x2: to.x - ux * TRIM,
    y2: to.y - uy * TRIM,
  }
}

/** SVG overlay (viewBox 0..100) drawing an arrow from each voter to their target. */
export default function VoteArrows({ votes, positions }) {
  const arrows = votes.filter(
    (v) =>
      v.target_id != null &&
      v.target_id !== v.voter_id &&
      positions[v.voter_id] &&
      positions[v.target_id]
  )
  return (
    <svg
      viewBox="0 0 100 100"
      className="pointer-events-none absolute inset-0 z-10 h-full w-full text-accent"
      aria-hidden="true"
    >
      <defs>
        <marker
          id="vote-arrowhead"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="currentColor" />
        </marker>
      </defs>
      {arrows.map((v) => (
        <line
          key={`${v.voter_id}-${v.target_id}`}
          data-testid="vote-arrow"
          {...shorten(positions[v.voter_id], positions[v.target_id])}
          stroke="currentColor"
          strokeWidth="0.7"
          strokeLinecap="round"
          markerEnd="url(#vote-arrowhead)"
        />
      ))}
    </svg>
  )
}
