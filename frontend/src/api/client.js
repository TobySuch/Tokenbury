export const fetchLocations = () => fetch('/api/locations/').then((r) => r.json())
