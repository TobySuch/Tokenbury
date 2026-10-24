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

test('asks for the banner of the given site', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false }))
  await act(async () => {
    render(<Banner site="werewolf" />)
  })
  expect(globalThis.fetch).toHaveBeenCalledWith('/api/banner/?site=werewolf')
})

test('refetches when the site changes', async () => {
  globalThis.fetch = vi.fn((url) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({ id: 1, text: url.endsWith('werewolf') ? 'Wolf news' : 'Town news' }),
    })
  )
  let rerender
  await act(async () => {
    ;({ rerender } = render(<Banner site="town" />))
  })
  expect(screen.getByText('Town news')).toBeInTheDocument()
  await act(async () => {
    rerender(<Banner site="werewolf" />)
  })
  expect(screen.getByText('Wolf news')).toBeInTheDocument()
})
