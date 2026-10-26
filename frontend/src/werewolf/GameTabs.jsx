import { Link } from 'react-router-dom'
import Pill from '../components/ui/Pill'

const RESULT = {
  wolves: 'Wolves won',
  town: 'Town won',
  lovers: 'Lovers won',
  draw: 'Draw',
}

function status(game) {
  if (game.status === 'active') return <Pill tone="live">Live</Pill>
  if (game.winner) return <Pill>{RESULT[game.winner] ?? 'Over'}</Pill>
  return null
}

// One tab per published game, oldest on the left. Games arrive newest first.
export default function GameTabs({ games, selectedId }) {
  return (
    <nav className="border-b border-rule bg-paper px-4">
      <div
        role="tablist"
        aria-label="Games"
        className="mx-auto flex max-w-6xl gap-1 overflow-x-auto pt-2"
      >
        {[...games].reverse().map((game, i) => {
          const selected = game.id === selectedId
          return (
            <Link
              key={game.id}
              to={`/werewolf/${game.id}`}
              role="tab"
              aria-selected={selected}
              // Keep the selected (usually newest, rightmost) tab visible when the bar scrolls.
              ref={
                selected
                  ? (el) => el?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
                  : undefined
              }
              data-testid={`game-tab-${game.id}`}
              className={`-mb-px flex shrink-0 items-center gap-2 rounded-t-lg border px-4 py-2 font-semibold whitespace-nowrap transition-colors ${
                selected
                  ? 'border-rule border-b-chip bg-chip text-ink'
                  : 'border-transparent text-ink-muted hover:bg-paper-hover hover:text-ink'
              }`}
            >
              Game {i + 1}
              {status(game)}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
