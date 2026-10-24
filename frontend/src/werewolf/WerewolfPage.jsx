import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import StepControls from '../components/ui/StepControls'
import PlayerCircle from './PlayerCircle'
import PlayerSidebar from './PlayerSidebar'
import { fetchGames, fetchPlayers } from './api'
import { useBeats } from './useBeats'

function Spectator({ gameId, game, beats, players }) {
  const [follow, setFollow] = useState(() => game.status === 'active')
  const [pos, setPos] = useState(0)
  const [hoveredId, setHoveredId] = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  const last = beats.length - 1
  const index = follow ? last : Math.min(pos, last)
  const beat = beats[index]

  const stepTo = (i) => {
    setFollow(false)
    setPos(Math.max(0, Math.min(i, last)))
  }

  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(e.target?.tagName)) return
      if (e.key === 'ArrowLeft') stepTo(index - 1)
      if (e.key === 'ArrowRight') stepTo(index + 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const aliveIds = new Set(beat?.alive_ids ?? players.map((p) => p.id))
  const focusId = hoveredId ?? selectedId
  const focused = players.find((p) => p.id === focusId) ?? null
  const night = beat?.palette === 'night'

  return (
    <div
      data-testid="werewolf-root"
      className={`${night ? 'theme-night' : ''} flex-1 bg-paper px-4 py-4 text-ink transition-colors duration-500`}
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <PlayerCircle
            players={players}
            beat={beat}
            aliveIds={aliveIds}
            hoveredId={hoveredId}
            selectedId={selectedId}
            onHover={setHoveredId}
            onSelect={(id) => setSelectedId((cur) => (cur === id ? null : id))}
          />
          <PlayerSidebar
            gameId={gameId}
            player={focused}
            alive={focused ? aliveIds.has(focused.id) : false}
            seq={beat?.seq}
            players={players}
          />
        </div>
        {beats.length === 0 ? (
          <p className="text-center italic text-ink-muted">The game has not started yet.</p>
        ) : (
          <StepControls
            index={index}
            count={beats.length}
            label={`Step ${index + 1} of ${beats.length}`}
            isLive={follow}
            canPrev={index > 0}
            canNext={index < last}
            onPrev={() => stepTo(index - 1)}
            onNext={() => stepTo(index + 1)}
            onScrub={stepTo}
            onLive={() => setFollow(true)}
            scrubLabel="Scrub through steps"
          />
        )}
      </div>
    </div>
  )
}

function GameView({ gameId }) {
  const { game, beats } = useBeats(gameId)
  const [players, setPlayers] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchPlayers(gameId).then((data) => {
      if (!cancelled) setPlayers(data)
    })
    return () => {
      cancelled = true
    }
  }, [gameId])

  // Beats have loaded but the game hasn't: it doesn't exist or isn't published.
  if (beats && !game) {
    return (
      <p className="flex-1 p-8 text-center italic text-ink-muted">
        This game isn&rsquo;t available.
      </p>
    )
  }
  if (!game || !beats || !players) {
    return <p className="flex-1 p-8 text-center italic text-ink-muted">Gathering the players…</p>
  }
  return <Spectator gameId={gameId} game={game} beats={beats} players={players} />
}

export default function WerewolfPage() {
  const { gameId } = useParams()
  const [latest, setLatest] = useState(undefined)

  useEffect(() => {
    if (gameId) return undefined
    let cancelled = false
    fetchGames().then((games) => {
      if (!cancelled) setLatest(games[0]?.id ?? null)
    })
    return () => {
      cancelled = true
    }
  }, [gameId])

  const id = gameId ?? latest
  if (id === undefined) {
    return <p className="flex-1 p-8 text-center italic text-ink-muted">Loading…</p>
  }
  if (id === null) {
    return (
      <p className="flex-1 p-8 text-center italic text-ink-muted">
        No werewolf games have been played yet.
      </p>
    )
  }
  return <GameView key={id} gameId={id} />
}
