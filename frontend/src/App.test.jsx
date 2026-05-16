import { render, screen, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

beforeEach(() => {
  globalThis.fetch = vi.fn((url) => {
    if (url === '/api/instance/') {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 1,
            name: 'Test',
            slug: 'test',
            map_image_url: '/media/maps/test.png',
          }),
      })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('App renders the page heading', async () => {
  await act(async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )
  })
  expect(screen.getAllByRole('img', { name: 'Tokenbury-on-Sea' }).length).toBeGreaterThan(0)
})

test('App renders the town map image', async () => {
  await act(async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )
  })
  expect(screen.getByRole('img', { name: /tokenbury.*map/i })).toBeInTheDocument()
})
