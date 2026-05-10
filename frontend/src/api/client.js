export const fetchLocations = () => fetch('/api/locations/').then((r) => r.json())

export const fetchLatestTick = () =>
  fetch('/api/ticks/latest/').then((r) => (r.ok ? r.json() : null))
