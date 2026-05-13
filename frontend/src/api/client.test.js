import { fetchInstance, fetchLatestTick, fetchTicks, fetchTickDays, fetchTickById } from './client'

afterEach(() => {
  vi.restoreAllMocks()
})

test('fetchInstance calls /api/instance/ and returns parsed data', async () => {
  const data = {
    id: 1,
    name: 'Tokenbury-on-Sea',
    slug: 'tokenbury-on-sea',
    map_image_url: '/media/maps/town.png',
  }
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(data) }))
  const result = await fetchInstance()
  expect(fetch).toHaveBeenCalledWith('/api/instance/')
  expect(result).toEqual(data)
})

test('fetchInstance returns null on non-ok response', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false }))
  expect(await fetchInstance()).toBeNull()
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

test('fetchTicks with no arg calls /api/ticks/', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }))
  await fetchTicks()
  expect(fetch).toHaveBeenCalledWith('/api/ticks/')
})

test('fetchTicks with date appends query param', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }))
  await fetchTicks('2024-01-01')
  expect(fetch).toHaveBeenCalledWith('/api/ticks/?date=2024-01-01')
})

test('fetchTicks returns empty array on non-ok response', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false }))
  expect(await fetchTicks()).toEqual([])
})

test('fetchTickDays calls /api/ticks/days/', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(['2024-01-01']) })
  )
  const result = await fetchTickDays()
  expect(fetch).toHaveBeenCalledWith('/api/ticks/days/')
  expect(result).toEqual(['2024-01-01'])
})

test('fetchTickDays returns empty array on non-ok response', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false }))
  expect(await fetchTickDays()).toEqual([])
})

test('fetchTickById calls correct URL', async () => {
  const data = { id: 5, agent_states: [] }
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(data) }))
  const result = await fetchTickById(5)
  expect(fetch).toHaveBeenCalledWith('/api/ticks/5/')
  expect(result).toEqual(data)
})

test('fetchTickById returns null on 404', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 404 }))
  expect(await fetchTickById(99)).toBeNull()
})
