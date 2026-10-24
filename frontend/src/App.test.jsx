import { render, screen, act, within } from '@testing-library/react'
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
    if (url === '/api/banner/') {
      return Promise.resolve({ ok: false })
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

test('App links to the werewolf page from both navs', async () => {
  await act(async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )
  })
  const links = screen.getAllByRole('link', { name: /werewolf/i })
  expect(links.length).toBe(2)
  links.forEach((l) => expect(l).toHaveAttribute('href', '/werewolf'))
})

test('on the town site the werewolf logo sits next to the main logo with a Try: label', async () => {
  await act(async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    )
  })
  const header = screen.getByRole('banner')
  const tryLink = within(header).getByRole('link', { name: /try.*werewolf/i })
  expect(tryLink).toHaveAttribute('href', '/werewolf')
  expect(tryLink).toHaveTextContent('Try:')
  expect(within(tryLink).getByRole('img')).toHaveAttribute('src', '/assets/werewolf-logo.png')
  expect(within(header).getByRole('heading', { level: 1 })).toContainElement(
    within(header).getByRole('img', { name: 'Tokenbury-on-Sea' })
  )
  // No separate Werewolf button in the header nav any more.
  expect(within(header).queryByRole('link', { name: 'Werewolf' })).toBeNull()
})

test('on the werewolf site the header uses the werewolf logo', async () => {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={['/werewolf']}>
        <App />
      </MemoryRouter>
    )
  })
  const header = screen.getByRole('banner')
  const heading = within(header).getByRole('heading', { level: 1 })
  const logo = within(heading).getByRole('img', { name: 'Tokenbury Werewolf' })
  expect(logo).toHaveAttribute('src', '/assets/werewolf-logo.png')
  expect(within(heading).getByRole('link')).toHaveAttribute('href', '/werewolf')
  const back = within(header).getByRole('link', { name: /back to.*tokenbury-on-sea/i })
  expect(back).toHaveAttribute('href', '/')
})
