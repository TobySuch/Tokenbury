export const fetchLocations = () => fetch('/api/locations/').then((r) => r.json())

export const fetchLatestTick = (lastTickId = null) => {
  const url =
    lastTickId != null ? `/api/ticks/latest/?last_tick_id=${lastTickId}` : '/api/ticks/latest/'
  return fetch(url).then((r) => {
    if (r.status === 304) return null
    return r.ok ? r.json() : null
  })
}
