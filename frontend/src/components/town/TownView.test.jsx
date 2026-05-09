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

function mockFetch(data) {
  globalThis.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve(data) }))
}

afterEach(() => {
  vi.restoreAllMocks()
})

test('renders the map image', () => {
  mockFetch([])
  render(<TownView />)
  expect(screen.getByRole('img', { name: /tokenbury/i })).toBeInTheDocument()
})

test('renders a bounding box for each location after image loads', async () => {
  mockFetch(LOCATIONS)

  await act(async () => {
    render(<TownView />)
  })

  const img = screen.getByRole('img')
  Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })

  await act(async () => {
    fireEvent.load(img)
  })

  expect(screen.getByTitle('Harbour Café')).toBeInTheDocument()
  expect(screen.getByTitle('The Anchor')).toBeInTheDocument()
})

test('shows location names inside the bounding boxes', async () => {
  mockFetch(LOCATIONS)

  await act(async () => {
    render(<TownView />)
  })

  const img = screen.getByRole('img')
  Object.defineProperty(img, 'naturalWidth', { value: 1000, configurable: true })
  Object.defineProperty(img, 'naturalHeight', { value: 800, configurable: true })

  await act(async () => {
    fireEvent.load(img)
  })

  expect(screen.getByText('Harbour Café')).toBeInTheDocument()
  expect(screen.getByText('The Anchor')).toBeInTheDocument()
})

test('no bounding boxes rendered before image loads', async () => {
  mockFetch(LOCATIONS)

  await act(async () => {
    render(<TownView />)
  })

  expect(screen.queryByTitle('Harbour Café')).not.toBeInTheDocument()
})
