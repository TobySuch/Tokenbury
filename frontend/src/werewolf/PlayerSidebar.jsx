import { useEffect, useState } from 'react'
import Panel from '../components/ui/Panel'
import Pill from '../components/ui/Pill'
import { fetchNotes } from './api'

export default function PlayerSidebar({ gameId, player, alive, seq }) {
  const key = player && seq != null ? `${player.id}:${seq}` : null
  const [loaded, setLoaded] = useState({ key: null, text: '' })

  useEffect(() => {
    if (!key) return undefined
    let cancelled = false
    fetchNotes(gameId, player.id, seq).then((data) => {
      if (!cancelled) setLoaded({ key, text: data?.text ?? '' })
    })
    return () => {
      cancelled = true
    }
  }, [gameId, key, player?.id, seq])

  return (
    <Panel data-testid="player-sidebar" className="p-4 transition-colors duration-500">
      {!player ? (
        <p className="text-sm italic text-ink-muted">Hover or tap a player to see their details</p>
      ) : (
        <div className="flex flex-col gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-bold italic">{player.name}</h2>
              <Pill tone={player.role}>{player.role}</Pill>
            </div>
            <p className="mt-1 text-sm text-ink-muted">
              {player.wolf_label ? `${player.wolf_label} · ` : ''}
              {alive ? 'Alive' : 'Dead'}
            </p>
          </div>
          <div className="border-l-2 border-rule pl-3">
            <p className="text-xs font-semibold text-ink-muted">Private notes at this step</p>
            <p
              data-testid="player-notes"
              tabIndex={0}
              className="mt-0.5 max-h-24 overflow-y-auto overscroll-contain whitespace-pre-wrap pr-1 text-sm text-ink-soft sm:max-h-48 lg:max-h-[50vh]"
            >
              {loaded.key !== key
                ? 'Loading…'
                : loaded.text || <span className="italic">No notes yet.</span>}
            </p>
          </div>
        </div>
      )}
    </Panel>
  )
}
