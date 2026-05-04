import { render, screen } from '@testing-library/react'
import App from './App'

beforeEach(() => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve({ status: 'ok', message: 'Tokenbury is alive 🌊' }),
    })
  )
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('App renders without crashing', () => {
  render(<App />)
})

test('App renders the connecting state before data loads', () => {
  render(<App />)
  expect(screen.getByText('Tokenbury-on-Sea')).toBeInTheDocument()
  expect(screen.getByText('Connecting...')).toBeInTheDocument()
})
