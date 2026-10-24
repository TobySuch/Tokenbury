import Pill from '../components/ui/Pill'
import SpeechBubble from './SpeechBubble'
import VoteArrows from './VoteArrows'

const RADIUS = 38

function seatPositions(players) {
  const ordered = [...players].sort((a, b) => a.seat - b.seat)
  const positions = {}
  ordered.forEach((p, i) => {
    const angle = (-90 + (360 * i) / ordered.length) * (Math.PI / 180)
    positions[p.id] = { x: 50 + RADIUS * Math.cos(angle), y: 50 + RADIUS * Math.sin(angle) }
  })
  return positions
}

function ListeningMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="absolute -right-1 -top-1 h-5 w-5 rounded-full bg-paper p-0.5 text-accent"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      <title>Listening</title>
      <path d="M8 8a5 5 0 0 1 0 8M12 5a9 9 0 0 1 0 14M16 2a13 13 0 0 1 0 20" />
    </svg>
  )
}

function Avatar({ player, className }) {
  return player.avatar_url ? (
    <img src={player.avatar_url} alt="" className={`rounded-full object-cover ${className}`} />
  ) : (
    <span
      aria-hidden="true"
      className={`flex items-center justify-center rounded-full bg-chip font-bold ${className}`}
    >
      {player.name.slice(0, 1)}
    </span>
  )
}

const WINNER_TEXT = {
  wolves: 'The wolves win',
  town: 'The town wins',
  draw: 'A draw: the game ran out of days',
}

// eslint-disable-next-line react-refresh/only-export-components
export function winnerText(winner) {
  return WINNER_TEXT[winner] ?? 'Game over'
}

export default function PlayerCircle({
  players,
  beat,
  aliveIds,
  hoveredId,
  selectedId,
  onHover,
  onSelect,
}) {
  const positions = seatPositions(players)
  const night = beat?.palette === 'night'
  const nameOf = Object.fromEntries(players.map((p) => [String(p.id), p.name]))
  const speakerId =
    beat && (beat.kind === 'speech' || beat.kind === 'wolf_message') ? beat.actor_id : null
  const tally = beat?.kind === 'vote_reveal' && beat.tally ? Object.entries(beat.tally) : null

  const isDimmed = (p) => {
    if (!beat) return false
    if (beat.kind === 'wolf_message') return p.id !== beat.actor_id
    return night && p.role !== 'wolf'
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative aspect-square w-full max-w-[34rem]">
        {beat?.kind === 'vote_reveal' && (
          <VoteArrows votes={beat.votes ?? []} positions={positions} />
        )}

        <div className="absolute inset-[24%] flex flex-col items-center justify-center gap-1 text-center">
          <h2
            data-testid="centre-banner"
            className="text-xl font-bold italic leading-tight sm:text-2xl"
          >
            {beat?.banner}
          </h2>
          {beat?.text && beat.kind !== 'speech' && beat.kind !== 'wolf_message' && (
            <p className="line-clamp-4 text-xs text-ink-soft sm:text-sm">{beat.text}</p>
          )}
          {beat?.kind === 'game_over' && (
            <p
              role="status"
              className="rounded-full bg-accent px-4 py-1 text-sm font-bold text-accent-ink"
            >
              {winnerText(beat.winner)}
            </p>
          )}
        </div>

        {players.map((p) => {
          const { x, y } = positions[p.id]
          const alive = aliveIds.has(p.id)
          const speaking = speakerId === p.id
          const dimmed = isDimmed(p)
          const focused = hoveredId === p.id || selectedId === p.id
          return (
            <div
              key={p.id}
              data-testid={`seat-${p.id}`}
              data-state={alive ? 'alive' : 'dead'}
              data-speaker={speaking ? 'true' : 'false'}
              data-dimmed={dimmed ? 'true' : 'false'}
              style={{ left: `${x}%`, top: `${y}%` }}
              className={`absolute flex w-[4.5rem] -translate-x-1/2 -translate-y-1/2 flex-col items-center transition-opacity duration-700 sm:w-24 ${
                speaking ? 'z-30' : 'z-20'
              } ${!alive ? 'opacity-50' : dimmed ? 'opacity-35' : 'opacity-100'}`}
              onMouseEnter={() => onHover(p.id)}
              onMouseLeave={() => onHover(null)}
              onClick={() => onSelect(p.id)}
            >
              <button
                type="button"
                aria-label={p.name}
                onFocus={() => onHover(p.id)}
                onBlur={() => onHover(null)}
                className={`relative flex min-h-[44px] min-w-[44px] cursor-pointer flex-col items-center rounded-full p-1 outline-offset-2 transition-colors ${
                  focused ? 'outline-2 outline-dashed outline-ink' : ''
                } ${
                  speaking ? 'bg-accent text-accent-ink' : ''
                } ${!alive ? 'border-2 border-dashed border-ink-muted' : ''}`}
              >
                <Avatar
                  player={p}
                  className="h-11 w-11 border border-rule text-lg sm:h-14 sm:w-14"
                />
                <span className="mt-0.5 max-w-full truncate text-xs font-semibold">{p.name}</span>
                {night && p.role === 'seer' && alive && <ListeningMark />}
              </button>
              {!alive && (
                <Pill tone={p.role} className="mt-0.5">
                  {p.role}
                </Pill>
              )}
              {speaking && beat.text && <SpeechBubble text={beat.text} x={x} y={y} />}
            </div>
          )
        })}
      </div>

      {tally && (
        <ul
          data-testid="vote-tally"
          className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-sm"
        >
          {tally
            .sort((a, b) => b[1] - a[1])
            .map(([id, count]) => (
              <li key={id}>
                <span className="font-semibold">
                  {id === 'none' ? 'No one' : (nameOf[id] ?? `Player ${id}`)}
                </span>{' '}
                {count}
              </li>
            ))}
        </ul>
      )}
    </div>
  )
}
