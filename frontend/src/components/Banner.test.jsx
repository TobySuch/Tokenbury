import { render, screen, act } from '@testing-library/react'
import Banner from './Banner'

afterEach(() => {
  vi.restoreAllMocks()
})

test('renders the banner text when an active banner is returned', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          id: 1,
          text: 'The simulation is paused.',
          created_at: '2026-01-01T00:00:00Z',
        }),
    })
  )
  await act(async () => {
    render(<Banner />)
  })
  expect(screen.getByText('The simulation is paused.')).toBeInTheDocument()
})

test('renders nothing when there is no active banner', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false }))
  const { container } = render(<Banner />)
  await act(async () => {})
  expect(container).toBeEmptyDOMElement()
})
