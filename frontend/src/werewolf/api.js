const base = '/api/werewolf/games'

export const fetchGames = () => fetch(`${base}/`).then((r) => (r.ok ? r.json() : []))

export const fetchGame = (gameId) =>
  fetch(`${base}/${gameId}/`).then((r) => (r.ok ? r.json() : null))

export const fetchPlayers = (gameId) =>
  fetch(`${base}/${gameId}/players/`).then((r) => (r.ok ? r.json() : []))

export const fetchBeats = (gameId, after = null) => {
  const url = after != null ? `${base}/${gameId}/beats/?after=${after}` : `${base}/${gameId}/beats/`
  return fetch(url).then((r) => (r.ok ? r.json() : []))
}

export const fetchNotes = (gameId, playerId, at) =>
  fetch(`${base}/${gameId}/notes/?player=${playerId}&at=${at}`).then((r) =>
    r.ok ? r.json() : null
  )
