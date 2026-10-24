import { useEffect, useRef, useState } from 'react'
import { fetchBeats, fetchGame } from './api'

export const POLL_MS = 5000

/**
 * Loads every beat for a game, then polls for new ones (using `after=<last index>`)
 * for as long as the game is active. `beats` and `game` are null until first load.
 */
export function useBeats(gameId) {
  const [game, setGame] = useState(null)
  const [beats, setBeats] = useState(null)
  const lastIndex = useRef(null)
  const active = game?.status === 'active'

  useEffect(() => {
    lastIndex.current = beats && beats.length ? beats[beats.length - 1].index : null
  }, [beats])

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchGame(gameId), fetchBeats(gameId)]).then(([g, all]) => {
      if (cancelled) return
      setGame(g)
      setBeats(all)
    })
    return () => {
      cancelled = true
    }
  }, [gameId])

  useEffect(() => {
    if (!active) return undefined
    let cancelled = false
    const merge = (fresh) => {
      if (fresh.length === 0) return
      setBeats((prev) => {
        const last = prev.length ? prev[prev.length - 1].index : -1
        const added = fresh.filter((b) => b.index > last)
        return added.length ? [...prev, ...added] : prev
      })
    }
    const id = setInterval(async () => {
      const [g, fresh] = await Promise.all([
        fetchGame(gameId),
        fetchBeats(gameId, lastIndex.current),
      ])
      if (cancelled) return
      if (g) setGame(g)
      merge(fresh)
      if (g && g.status !== 'active') {
        // The game and beats requests race: once the game has ended, take one
        // last look so the final beats (death / game_over) are not missed.
        const after = fresh.length ? fresh[fresh.length - 1].index : lastIndex.current
        const rest = await fetchBeats(gameId, after)
        if (!cancelled) merge(rest)
      }
    }, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [gameId, active])

  return { game, beats }
}
