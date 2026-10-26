import { render, screen, act, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { winnerText } from './PlayerCircle'
import WerewolfPage from './WerewolfPage'

const NAMES = ['Alice', 'Bram', 'Cora', 'Dave', 'Edie', 'Finn', 'Gus']
const ROLES = ['wolf', 'wolf', 'seer', 'villager', 'villager', 'villager', 'villager']
const PLAYERS = NAMES.map((name, i) => ({
  id: i + 1,
  name,
  seat: i + 1,
  avatar_url: null,
  role: ROLES[i],
  wolf_label: ROLES[i] === 'wolf' ? (i === 0 ? 'Wolf A' : 'Wolf B') : null,
  alive: true,
}))
const ALL = [1, 2, 3, 4, 5, 6, 7]
const NO_DAVE = [1, 2, 3, 5, 6, 7]

const beat = (index, extra) => ({
  index,
  seq: index * 3 + 1,
  day: 1,
  phase: 'discussion',
  kind: 'speech',
  palette: 'day',
  banner: 'Day 1: Discussion',
  actor_id: null,
  text: null,
  kill_target_id: null,
  victim_id: null,
  role: null,
  votes: [],
  tally: null,
  winner: null,
  alive_ids: ALL,
  ...extra,
})

const BEATS = [
  beat(0, { kind: 'phase_change', phase: 'night', palette: 'night', banner: 'Night 1' }),
  beat(1, {
    kind: 'wolf_message',
    phase: 'night',
    palette: 'night',
    banner: 'Night 1',
    actor_id: 1,
    text: "Let's take Dave",
  }),
  beat(2, {
    kind: 'morning',
    banner: 'Day 1: Morning',
    victim_id: 4,
    role: 'villager',
    text: 'Dave was found dead',
    alive_ids: NO_DAVE,
  }),
  beat(3, { actor_id: 5, text: 'I suspect Alice', alive_ids: NO_DAVE }),
  beat(4, {
    kind: 'vote_reveal',
    banner: 'Day 1: Vote',
    alive_ids: NO_DAVE,
    votes: [
      { voter_id: 5, target_id: 1 },
      { voter_id: 6, target_id: 1 },
      { voter_id: 3, target_id: null },
    ],
    tally: { 1: 2, none: 1 },
  }),
  beat(5, {
    kind: 'game_over',
    banner: 'Game over',
    winner: 'town',
    alive_ids: NO_DAVE,
  }),
]

function mockApi({ status = 'completed', beats = BEATS, games } = {}) {
  const state = { beats: [...beats], status }
  globalThis.fetch = vi.fn((url) => {
    const ok = (body) => Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
    const game = (id) => ({
      id,
      status: state.status,
      phase: 'discussion',
      day_number: 1,
      winner: null,
      created_at: '2026-10-30T00:00:00Z',
    })
    if (url === '/api/werewolf/games/') return ok(games ?? [game(7)])
    if (/^\/api\/werewolf\/games\/\d+\/$/.test(url)) return ok(game(7))
    if (url.endsWith('/players/')) return ok(PLAYERS)
    if (url.includes('/beats/')) {
      const m = url.match(/after=(-?\d+)/)
      const after = m ? Number(m[1]) : -1
      return ok(state.beats.filter((b) => b.index > after))
    }
    if (url.includes('/notes/')) {
      const q = new URL(url, 'http://x').searchParams
      return ok({
        player_id: Number(q.get('player')),
        version: 1,
        text: `notes@${q.get('at')}`,
        at_seq: Number(q.get('at')),
      })
    }
    return Promise.resolve({ ok: false })
  })
  return state
}

async function renderPage(path = '/werewolf/7') {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/werewolf" element={<WerewolfPage />} />
          <Route path="/werewolf/:gameId" element={<WerewolfPage />} />
        </Routes>
      </MemoryRouter>
    )
  })
}

const next = () => fireEvent.click(screen.getByRole('button', { name: 'Next' }))
const back = () => fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
const banner = () => screen.getByTestId('centre-banner')

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('stepping', () => {
  test('a finished game starts at step 1 and next/back change the displayed beat', async () => {
    mockApi()
    await renderPage()
    expect(screen.getByText('Step 1 of 6')).toBeInTheDocument()
    expect(banner()).toHaveTextContent('Night 1')
    next()
    next()
    expect(screen.getByText('Step 3 of 6')).toBeInTheDocument()
    expect(banner()).toHaveTextContent('Day 1: Morning')
    back()
    expect(screen.getByText('Step 2 of 6')).toBeInTheDocument()
  })

  test('/werewolf loads the latest game', async () => {
    mockApi({
      games: [
        { id: 9, status: 'completed' },
        { id: 3, status: 'completed' },
      ],
    })
    await renderPage('/werewolf')
    const urls = globalThis.fetch.mock.calls.map((c) => c[0])
    expect(urls.some((u) => u.startsWith('/api/werewolf/games/9/'))).toBe(true)
  })

  test('arrow keys step through beats', async () => {
    mockApi()
    await renderPage()
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(screen.getByText('Step 2 of 6')).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(screen.getByText('Step 1 of 6')).toBeInTheDocument()
  })
})

describe('palette', () => {
  test('night beats use the night theme and day beats do not', async () => {
    mockApi()
    await renderPage()
    const root = screen.getByTestId('werewolf-root')
    expect(root).toHaveClass('theme-night')
    next()
    expect(root).toHaveClass('theme-night')
    next()
    expect(root).not.toHaveClass('theme-night')
  })

  test('at night only wolves are lit and the seer is marked listening', async () => {
    mockApi()
    await renderPage()
    expect(screen.getByTestId('seat-1')).toHaveAttribute('data-dimmed', 'false')
    expect(screen.getByTestId('seat-4')).toHaveAttribute('data-dimmed', 'true')
    expect(within(screen.getByTestId('seat-3')).getByTitle('Listening')).toBeInTheDocument()
  })
})

describe('beats', () => {
  test('wolf message puts a bubble on the wolf and dims everyone else', async () => {
    mockApi()
    await renderPage()
    next()
    const seat = screen.getByTestId('seat-1')
    expect(seat).toHaveAttribute('data-speaker', 'true')
    expect(within(seat).getByText("Let's take Dave")).toBeInTheDocument()
    expect(screen.getByTestId('seat-2')).toHaveAttribute('data-dimmed', 'true')
  })

  test('morning marks the victim dead with a role badge', async () => {
    mockApi()
    await renderPage()
    next()
    next()
    const dave = screen.getByTestId('seat-4')
    expect(dave).toHaveAttribute('data-state', 'dead')
    expect(within(dave).getByText('villager')).toBeInTheDocument()
    expect(screen.getByTestId('seat-5')).toHaveAttribute('data-state', 'alive')
    expect(within(screen.getByTestId('seat-5')).queryByText('villager')).toBeNull()
  })

  test('speech shows a bubble on the speaker', async () => {
    mockApi()
    await renderPage()
    for (let i = 0; i < 3; i++) next()
    const seat = screen.getByTestId('seat-5')
    expect(seat).toHaveAttribute('data-speaker', 'true')
    expect(within(seat).getByText('I suspect Alice')).toBeInTheDocument()
  })

  test('vote reveal draws arrows for each vote with a target, plus the tally', async () => {
    mockApi()
    await renderPage()
    for (let i = 0; i < 4; i++) next()
    expect(screen.getAllByTestId('vote-arrow')).toHaveLength(2)
    const tally = screen.getByTestId('vote-tally')
    expect(tally).toHaveTextContent('Alice')
    expect(tally).toHaveTextContent('2')
    expect(tally).toHaveTextContent(/no one/i)
  })

  test('game over shows the winner', async () => {
    mockApi()
    await renderPage()
    for (let i = 0; i < 5; i++) next()
    expect(screen.getByRole('status')).toHaveTextContent(/town wins/i)
  })
})

describe('live mode and polling', () => {
  const setup = async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false })
    const state = mockApi({ status: 'active', beats: BEATS.slice(0, 3) })
    await renderPage()
    return state
  }
  const tick = () =>
    act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })

  test('an active game starts live and follows new beats, polling with after=<last index>', async () => {
    const state = await setup()
    expect(screen.getByText('Step 3 of 3')).toBeInTheDocument()
    state.beats.push(BEATS[3])
    await tick()
    expect(screen.getByText('Step 4 of 4')).toBeInTheDocument()
    const urls = globalThis.fetch.mock.calls.map((c) => c[0])
    expect(urls.some((u) => u.includes('/beats/?after=2'))).toBe(true)
  })

  test('a viewer who stepped back stays put until pressing Live', async () => {
    const state = await setup()
    back()
    expect(screen.getByText('Step 2 of 3')).toBeInTheDocument()
    state.beats.push(BEATS[3])
    await tick()
    expect(screen.getByText('Step 2 of 4')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Go to live' }))
    expect(screen.getByText('Step 4 of 4')).toBeInTheDocument()
    state.beats.push(BEATS[4])
    await tick()
    expect(screen.getByText('Step 5 of 5')).toBeInTheDocument()
  })

  test('stops polling when the game is no longer active', async () => {
    const state = await setup()
    state.status = 'completed'
    await tick()
    const before = globalThis.fetch.mock.calls.length
    await tick()
    await tick()
    expect(globalThis.fetch.mock.calls.length).toBe(before)
  })
})

describe('sidebar', () => {
  test('hovering a player shows role, label, status and notes as of the current beat', async () => {
    mockApi()
    await renderPage()
    fireEvent.mouseEnter(screen.getByTestId('seat-1'))
    const sidebar = screen.getByTestId('player-sidebar')
    expect(sidebar).toHaveTextContent('Alice')
    expect(sidebar).toHaveTextContent('Wolf A')
    expect(sidebar).toHaveTextContent(/alive/i)
    expect(await within(sidebar).findByText(`notes@${BEATS[0].seq}`)).toBeInTheDocument()
    const urls = globalThis.fetch.mock.calls.map((c) => c[0])
    expect(urls).toContain(`/api/werewolf/games/7/notes/?player=1&at=${BEATS[0].seq}`)
  })

  test('stepping changes the notes snapshot requested', async () => {
    mockApi()
    await renderPage()
    fireEvent.mouseEnter(screen.getByTestId('seat-1'))
    next()
    expect(await screen.findByText(`notes@${BEATS[1].seq}`)).toBeInTheDocument()
  })

  test('tapping selects a player', async () => {
    mockApi()
    await renderPage()
    fireEvent.click(screen.getByTestId('seat-4'))
    expect(screen.getByTestId('player-sidebar')).toHaveTextContent('Dave')
    expect(screen.getByTestId('player-sidebar')).toHaveTextContent(/villager/i)
  })
})

describe('game tabs', () => {
  const GAMES = [
    { id: 9, status: 'active', winner: null },
    { id: 3, status: 'finished', winner: 'wolves' },
  ]
  const tab = (id) => screen.getByTestId(`game-tab-${id}`)

  test('/werewolf shows a tab per game and selects the newest', async () => {
    mockApi({ games: GAMES })
    await renderPage('/werewolf')
    expect(screen.getAllByRole('tab')).toHaveLength(2)
    expect(tab(9)).toHaveAttribute('aria-selected', 'true')
    expect(tab(3)).toHaveAttribute('aria-selected', 'false')
    expect(tab(9)).toHaveTextContent('Game 2')
    expect(tab(3)).toHaveTextContent('Game 1')
  })

  test('tabs show Live for an active game and the result for a finished one', async () => {
    mockApi({ games: GAMES })
    await renderPage('/werewolf')
    expect(within(tab(9)).getByText('Live')).toBeInTheDocument()
    expect(within(tab(3)).getByText('Wolves won')).toBeInTheDocument()
  })

  test('clicking an older tab loads that game', async () => {
    mockApi({ games: GAMES })
    await renderPage('/werewolf')
    await act(async () => {
      fireEvent.click(tab(3))
    })
    expect(tab(3)).toHaveAttribute('aria-selected', 'true')
    const urls = globalThis.fetch.mock.calls.map((c) => c[0])
    expect(urls).toContain('/api/werewolf/games/3/beats/')
  })

  test('a direct link to an older game selects its tab', async () => {
    mockApi({ games: GAMES })
    await renderPage('/werewolf/3')
    expect(tab(3)).toHaveAttribute('aria-selected', 'true')
    expect(tab(9)).toHaveAttribute('aria-selected', 'false')
  })
})

describe('winnerText', () => {
  test.each([
    ['wolves', 'The wolves win'],
    ['town', 'The town wins'],
    ['draw', 'A draw: the game ran out of days'],
  ])('%s', (winner, text) => {
    expect(winnerText(winner)).toBe(text)
  })
})

test('a game that is missing or unpublished shows a not-found message', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 404 }))
  await renderPage('/werewolf/99')
  expect(screen.getByText(/this game isn.t available/i)).toBeInTheDocument()
  expect(screen.queryByText(/gathering the players/i)).toBeNull()
})
