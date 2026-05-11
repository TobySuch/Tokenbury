import { render, screen, act } from '@testing-library/react'
import App from './App'

beforeEach(() => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve([]) }))
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('App renders the page heading', async () => {
  await act(async () => {
    render(<App />)
  })
  expect(screen.getByText('Tokenbury-on-Sea')).toBeInTheDocument()
})

test('App renders the town map image', async () => {
  await act(async () => {
    render(<App />)
  })
  expect(screen.getByRole('img', { name: /tokenbury/i })).toBeInTheDocument()
})
