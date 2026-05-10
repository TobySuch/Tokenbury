const SIZE = 48

export default function AgentSprite({ name, spriteUrl }) {
  const shadow =
    'drop-shadow(0 0 6px rgba(255,255,255,0.9)) drop-shadow(0 0 12px rgba(255,255,255,0.7))'

  if (spriteUrl) {
    return (
      <img
        src={spriteUrl}
        alt={name}
        width={SIZE}
        height={SIZE}
        style={{
          width: SIZE,
          height: SIZE,
          objectFit: 'contain',
          filter: shadow,
          cursor: 'pointer',
        }}
      />
    )
  }
  return (
    <div
      style={{
        width: SIZE,
        height: SIZE,
        borderRadius: '50%',
        background: '#4b5563',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontSize: 16,
        fontWeight: 700,
        filter: shadow,
        cursor: 'pointer',
      }}
    >
      {name[0]}
    </div>
  )
}
