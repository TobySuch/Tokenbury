import { useEffect, useState } from 'react'
import CloseButton from '../components/ui/CloseButton'
import Panel from '../components/ui/Panel'
import Pill from '../components/ui/Pill'
import { fetchNotes } from './api'

export default function PlayerSidebar({ gameId, player, alive, seq, players = [], onClose }) {
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

  const partner = player?.lover_id != null ? players.find((p) => p.id === player.lover_id) : null

  return (
    <Panel data-testid="player-sidebar" className="p-4 transition-colors duration-500">
      {!player ? (
        <p className="text-sm italic text-ink-muted">Hover or tap a player to see their details</p>
      ) : (
        <div className="flex flex-col gap-3">
          <div>
            <div className="flex items-start gap-2">
              <div className="flex flex-1 flex-wrap items-center gap-2">
                <h2 className="text-xl font-bold italic">{player.name}</h2>
                <Pill tone={player.role}>{player.role}</Pill>
              </div>
              {onClose && (
                <CloseButton
                  label={`Deselect ${player.name}`}
                  onClick={onClose}
                  className="-mr-2 -mt-2"
                />
              )}
            </div>
            <p className="mt-1 text-sm text-ink-muted">
              {player.wolf_label ? `${player.wolf_label} · ` : ''}
              {alive ? 'Alive' : 'Dead'}
            </p>
            {partner && <p className="text-sm text-red-600">In love with {partner.name}</p>}
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
