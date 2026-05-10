import { fetchLatestTick } from './client'

afterEach(() => {
  vi.restoreAllMocks()
})

test('fetchLatestTick with no arg calls /api/ticks/latest/', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ id: 1 }) })
  )
  await fetchLatestTick()
  expect(fetch).toHaveBeenCalledWith('/api/ticks/latest/')
})

test('fetchLatestTick with lastTickId appends query param', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ id: 5 }) })
  )
  await fetchLatestTick(5)
  expect(fetch).toHaveBeenCalledWith('/api/ticks/latest/?last_tick_id=5')
})

test('fetchLatestTick returns parsed JSON on 200', async () => {
  const data = { id: 1, agent_states: [] }
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(data) })
  )
  expect(await fetchLatestTick()).toEqual(data)
})

test('fetchLatestTick returns null on 304', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ status: 304, ok: false }))
  expect(await fetchLatestTick(1)).toBeNull()
})

test('fetchLatestTick returns null on non-ok response', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ status: 404, ok: false }))
  expect(await fetchLatestTick()).toBeNull()
})
