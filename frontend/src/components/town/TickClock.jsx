export default function TickClock({ inGameTime }) {
  if (!inGameTime) return null
  const d = new Date(inGameTime)
  const day = d.toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })
  const date = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
  const time = d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  })
  return (
    <div className="pointer-events-none absolute top-2 left-2 rounded-lg bg-black/50 px-3 py-1.5 font-mono text-sm leading-none text-amber-100 backdrop-blur-sm">
      {day} {date} · {time}
    </div>
  )
}
