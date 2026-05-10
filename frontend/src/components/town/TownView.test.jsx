import { render, screen, act, fireEvent } from '@testing-library/react'
import TownView from './TownView'

const LOCATIONS = [
  {
    id: 1,
    slug: 'harbour_cafe',
    name: 'Harbour Café',
    description: 'A cosy café overlooking the harbour.',
    bbox_x1: 100,
    bbox_y1: 200,
    bbox_x2: 300,
    bbox_y2: 400,
  },
  {
    id: 2,
    slug: 'pub',
    name: 'The Anchor',
    description: 'The local pub.',
    bbox_x1: 400,
    bbox_y1: 100,
    bbox_x2: 600,
    bbox_y2: 300,
  },
]

const TICK_WITH_AGENTS = {
  id: 1,
  in_game_time: '2026-05-10T09:00:00Z',
  created_at: '2026-05-10T09:01:00Z',
  agent_states: [
    {
      agent_id: 1,
      agent_name: 'Margaret',
      agent_sprite_url: '/media/sprites/margaret.png',
      location_slug: 'harbour_cafe',
      activity: 'Reading the newspaper',
      mood: 'content',
      inner_thought: 'Quiet morning.',
    },
    {
      agent_id: 2,
      agent_name: 'Derek',
      agent_sprite_url: null,
      location_slug: 'harbour_cafe',
      activity: 'Eating toast',
      mood: 'cheerful',
      inner_thought: 'Good toast.',
    },
  ],
}

function mockFetch({ locations = LOCATIONS, tick = null } = {}) {
  globalThis.fetch = vi.fn((url) => {
    if (url.includes('/api/ticks/latest/')) {
      if (tick === null) return Promise.resolve({ ok: false })
      return Promise.resolve({ ok: true, json: () => Promise.resolve(tick) })
    }
    return Promise.resolve({ json: () => Promise.resolve(locations) })
  })
}

function setDebugMode(on) {
  Object.defineProperty(window, 'location', {
    value: { ...window.location, search: on ? '?debug=1' : '' },
    configurable: true,
    writable: true,
  })
}

async function renderWithImageLoad(options) {
  mockFetch(options)
  await act(async () => {
    render(<TownView />)
  })
  const img = screen.getByRole('img', { name: /tokenbury/i })
  Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })
  await act(async () => {
    fireEvent.load(img)
  })
  return img
}

afterEach(() => {
  vi.restoreAllMocks()
  setDebugMode(false)
})

test('renders the map image', () => {
  mockFetch()
  render(<TownView />)
  expect(screen.getByRole('img', { name: /tokenbury/i })).toBeInTheDocument()
})

test('renders a bounding box for each location after image loads in debug mode', async () => {
  setDebugMode(true)
  await renderWithImageLoad({ locations: LOCATIONS })
  expect(screen.getByTitle('Harbour Café')).toBeInTheDocument()
  expect(screen.getByTitle('The Anchor')).toBeInTheDocument()
})

test('shows location names inside the bounding boxes in debug mode', async () => {
  setDebugMode(true)
  await renderWithImageLoad({ locations: LOCATIONS })
  expect(screen.getByText('Harbour Café')).toBeInTheDocument()
  expect(screen.getByText('The Anchor')).toBeInTheDocument()
})

test('no bounding boxes rendered before image loads', async () => {
  setDebugMode(true)
  mockFetch({ locations: LOCATIONS })
  await act(async () => {
    render(<TownView />)
  })
  expect(screen.queryByTitle('Harbour Café')).not.toBeInTheDocument()
})

test('no bounding boxes rendered without debug mode', async () => {
  await renderWithImageLoad({ locations: LOCATIONS })
  expect(screen.queryByTitle('Harbour Café')).not.toBeInTheDocument()
  expect(screen.queryByTitle('The Anchor')).not.toBeInTheDocument()
})

test('shows coords on mouse move over image in debug mode', async () => {
  setDebugMode(true)
  mockFetch({ locations: [] })
  await act(async () => {
    render(<TownView />)
  })
  const img = screen.getByRole('img', { name: /tokenbury/i })
  Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })
  await act(async () => {
    fireEvent.load(img)
  })
  const container = img.parentElement
  vi.spyOn(container, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width: 1000,
    height: 800,
    right: 1000,
    bottom: 800,
  })
  await act(async () => {
    fireEvent.mouseMove(container, { clientX: 100, clientY: 200 })
  })
  expect(screen.getByText('100, 200')).toBeInTheDocument()
})

test('renders a sprite for each agent in the latest tick', async () => {
  await renderWithImageLoad({ locations: LOCATIONS, tick: TICK_WITH_AGENTS })
  expect(screen.getByAltText('Margaret')).toBeInTheDocument()
})

test('renders a fallback for agents without a sprite url', async () => {
  await renderWithImageLoad({ locations: LOCATIONS, tick: TICK_WITH_AGENTS })
  expect(screen.getByText('D')).toBeInTheDocument()
})

test('two agents at the same location both appear', async () => {
  await renderWithImageLoad({ locations: LOCATIONS, tick: TICK_WITH_AGENTS })
  expect(screen.getByAltText('Margaret')).toBeInTheDocument()
  expect(screen.getByText('D')).toBeInTheDocument()
})

test('no sprites rendered when tick returns null', async () => {
  await renderWithImageLoad({ locations: LOCATIONS, tick: null })
  expect(screen.queryByRole('img', { name: /margaret/i })).not.toBeInTheDocument()
})

test('agents with no location_slug are skipped', async () => {
  const tickWithNullLoc = {
    ...TICK_WITH_AGENTS,
    agent_states: [{ ...TICK_WITH_AGENTS.agent_states[0], location_slug: null }],
  }
  await renderWithImageLoad({ locations: LOCATIONS, tick: tickWithNullLoc })
  expect(screen.queryByAltText('Margaret')).not.toBeInTheDocument()
})

describe('polling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function mockFetchForPolling(initialTick, subsequentTick) {
    let tickCallCount = 0
    globalThis.fetch = vi.fn((url) => {
      if (url === '/api/locations/') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(LOCATIONS) })
      }
      tickCallCount++
      if (tickCallCount === 1) {
        return Promise.resolve({
          status: 200,
          ok: true,
          json: () => Promise.resolve(initialTick),
        })
      }
      return Promise.resolve(subsequentTick)
    })
  }

  async function renderAndLoad(initialTick, subsequentTick) {
    mockFetchForPolling(initialTick, subsequentTick)
    await act(async () => {
      render(<TownView />)
    })
    const img = screen.getByRole('img', { name: /tokenbury/i })
    Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })
    await act(async () => {
      fireEvent.load(img)
    })
    return img
  }

  test('polls for latest tick after 30 seconds', async () => {
    await renderAndLoad(TICK_WITH_AGENTS, { status: 304, ok: false })
    const callsBefore = fetch.mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(30_000)
    })

    expect(fetch.mock.calls.length).toBeGreaterThan(callsBefore)
  })

  test('poll sends last_tick_id from the loaded tick', async () => {
    await renderAndLoad(TICK_WITH_AGENTS, { status: 304, ok: false })

    await act(async () => {
      vi.advanceTimersByTime(30_000)
    })

    const pollCalls = fetch.mock.calls.filter(([url]) =>
      url.includes(`last_tick_id=${TICK_WITH_AGENTS.id}`)
    )
    expect(pollCalls.length).toBeGreaterThan(0)
  })

  test('updates agents when poll returns a new tick', async () => {
    const newTick = {
      id: 2,
      in_game_time: '2026-05-10T10:00:00Z',
      created_at: '2026-05-10T10:01:00Z',
      agent_states: [{ ...TICK_WITH_AGENTS.agent_states[0], location_slug: 'pub' }],
    }
    await renderAndLoad(TICK_WITH_AGENTS, {
      status: 200,
      ok: true,
      json: () => Promise.resolve(newTick),
    })

    expect(screen.getByAltText('Margaret')).toBeInTheDocument()
    expect(screen.getByText('D')).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(30_000)
    })
    await act(async () => {})

    expect(screen.getByAltText('Margaret')).toBeInTheDocument()
    expect(screen.queryByText('D')).not.toBeInTheDocument()
  })
})
