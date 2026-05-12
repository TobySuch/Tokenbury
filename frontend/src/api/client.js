export const fetchLocations = () => fetch('/api/locations/').then((r) => r.json())

export const fetchAgentDetail = (agentId) =>
  fetch(`/api/agents/${agentId}/`).then((r) => (r.ok ? r.json() : null))

export const fetchLatestTick = (lastTickId = null) => {
  const url =
    lastTickId != null ? `/api/ticks/latest/?last_tick_id=${lastTickId}` : '/api/ticks/latest/'
  return fetch(url).then((r) => {
    if (r.status === 304) return null
    return r.ok ? r.json() : null
  })
}

export const fetchTicks = (date = null) => {
  const url = date ? `/api/ticks/?date=${date}` : '/api/ticks/'
  return fetch(url).then((r) => (r.ok ? r.json() : []))
}

export const fetchTickDays = () => fetch('/api/ticks/days/').then((r) => (r.ok ? r.json() : []))

export const fetchTickById = (id) =>
  fetch(`/api/ticks/${id}/`).then((r) => (r.ok ? r.json() : null))
