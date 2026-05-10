export default function AgentSprite({ name, spriteUrl, isActive, onHover, onHoverEnd, onClick }) {
  const shadow =
    'drop-shadow(0 0 6px rgba(255,255,255,0.9)) drop-shadow(0 0 12px rgba(255,255,255,0.7))'
  const activeOutline = isActive ? '3px solid white' : 'none'

  const shared = {
    cursor: 'pointer',
    filter: shadow,
    outline: activeOutline,
    outlineOffset: '2px',
    borderRadius: '50%',
  }

  if (spriteUrl) {
    return (
      <img
        src={spriteUrl}
        alt={name}
        className="w-8 h-8 lg:w-12 lg:h-12"
        style={{ objectFit: 'contain', ...shared }}
        onMouseEnter={onHover}
        onMouseLeave={onHoverEnd}
        onClick={onClick}
      />
    )
  }
  return (
    <div
      className="w-8 h-8 lg:w-12 lg:h-12 text-sm lg:text-base"
      style={{
        background: '#4b5563',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontWeight: 700,
        ...shared,
      }}
      onMouseEnter={onHover}
      onMouseLeave={onHoverEnd}
      onClick={onClick}
    >
      {name[0]}
    </div>
  )
}
