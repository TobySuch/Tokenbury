import { render, screen, fireEvent } from '@testing-library/react'
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

function setDebugMode(on) {
  Object.defineProperty(window, 'location', {
    value: { ...window.location, search: on ? '?debug=1' : '' },
    configurable: true,
    writable: true,
  })
}

function renderAndLoad(props = {}) {
  render(<TownView locations={LOCATIONS} {...props} />)
  const img = screen.getByRole('img', { name: /tokenbury/i })
  Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })
  fireEvent.load(img)
  return img
}

afterEach(() => {
  vi.restoreAllMocks()
  setDebugMode(false)
})

test('renders the map image', () => {
  render(<TownView />)
  expect(screen.getByRole('img', { name: /tokenbury/i })).toBeInTheDocument()
})

test('renders a bounding box for each location after image loads in debug mode', () => {
  setDebugMode(true)
  renderAndLoad()
  expect(screen.getByTitle('Harbour Café')).toBeInTheDocument()
  expect(screen.getByTitle('The Anchor')).toBeInTheDocument()
})

test('shows location names inside the bounding boxes in debug mode', () => {
  setDebugMode(true)
  renderAndLoad()
  expect(screen.getByText('Harbour Café')).toBeInTheDocument()
  expect(screen.getByText('The Anchor')).toBeInTheDocument()
})

test('no bounding boxes rendered before image loads', () => {
  setDebugMode(true)
  render(<TownView locations={LOCATIONS} />)
  expect(screen.queryByTitle('Harbour Café')).not.toBeInTheDocument()
})

test('no bounding boxes rendered without debug mode', () => {
  renderAndLoad()
  expect(screen.queryByTitle('Harbour Café')).not.toBeInTheDocument()
  expect(screen.queryByTitle('The Anchor')).not.toBeInTheDocument()
})

test('shows coords on mouse move over image in debug mode', () => {
  setDebugMode(true)
  render(<TownView locations={[]} />)
  const img = screen.getByRole('img', { name: /tokenbury/i })
  Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })
  fireEvent.load(img)
  const container = img.parentElement
  vi.spyOn(container, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width: 1000,
    height: 800,
    right: 1000,
    bottom: 800,
  })
  fireEvent.mouseMove(container, { clientX: 100, clientY: 200 })
  expect(screen.getByText('100, 200')).toBeInTheDocument()
})

test('renders a sprite for each agent in the tick', () => {
  renderAndLoad({ tickData: TICK_WITH_AGENTS })
  expect(screen.getByAltText('Margaret')).toBeInTheDocument()
})

test('renders a fallback for agents without a sprite url', () => {
  renderAndLoad({ tickData: TICK_WITH_AGENTS })
  expect(screen.getByText('D')).toBeInTheDocument()
})

test('two agents at the same location both appear', () => {
  renderAndLoad({ tickData: TICK_WITH_AGENTS })
  expect(screen.getByAltText('Margaret')).toBeInTheDocument()
  expect(screen.getByText('D')).toBeInTheDocument()
})

test('no sprites rendered when tickData is undefined', () => {
  renderAndLoad()
  expect(screen.queryByRole('img', { name: /margaret/i })).not.toBeInTheDocument()
})

test('agents with no location_slug are skipped', () => {
  const tickWithNullLoc = {
    ...TICK_WITH_AGENTS,
    agent_states: [{ ...TICK_WITH_AGENTS.agent_states[0], location_slug: null }],
  }
  renderAndLoad({ tickData: tickWithNullLoc })
  expect(screen.queryByAltText('Margaret')).not.toBeInTheDocument()
})

test('sprites update when tickData prop changes', () => {
  const newTick = {
    id: 2,
    in_game_time: '2026-05-10T10:00:00Z',
    created_at: '2026-05-10T10:01:00Z',
    agent_states: [{ ...TICK_WITH_AGENTS.agent_states[0], location_slug: 'pub' }],
  }
  const { rerender } = render(<TownView locations={LOCATIONS} tickData={TICK_WITH_AGENTS} />)
  const img = screen.getByRole('img', { name: /tokenbury/i })
  Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })
  fireEvent.load(img)

  expect(screen.getByAltText('Margaret')).toBeInTheDocument()
  expect(screen.getByText('D')).toBeInTheDocument()

  rerender(<TownView locations={LOCATIONS} tickData={newTick} />)

  expect(screen.getByAltText('Margaret')).toBeInTheDocument()
  expect(screen.queryByText('D')).not.toBeInTheDocument()
})
