import { render, screen, within, act } from '@testing-library/react'
import Pill from '../components/ui/Pill'
import PlayerCircle, { winnerText } from './PlayerCircle'
import PlayerSidebar from './PlayerSidebar'

const ROLES = ['wolf', 'seer', 'doctor', 'villager', 'villager', 'villager']
const makePlayers = (n = 6) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    name: `P${i + 1}`,
    seat: i + 1,
    avatar_url: null,
    role: ROLES[i] ?? 'villager',
    wolf_label: null,
    alive: true,
    lover_id: i === 3 ? 5 : i === 4 ? 4 : null,
  }))

const beat = (extra) => ({
  kind: 'speech',
  palette: 'day',
  banner: 'Banner',
  actor_id: null,
  text: null,
  kill_target_id: null,
  target_id: null,
  victim_id: null,
  role: null,
  votes: [],
  tally: null,
  winner: null,
  ...extra,
})

function renderCircle(players, b, alive) {
  const ids = new Set(alive ?? players.map((p) => p.id))
  return render(
    <PlayerCircle
      players={players}
      beat={b}
      aliveIds={ids}
      hoveredId={null}
      selectedId={null}
      onHover={() => {}}
      onSelect={() => {}}
    />
  )
}

const dimmed = (id) => screen.getByTestId(`seat-${id}`).dataset.dimmed

test('doctor pill has its own tone', () => {
  render(<Pill tone="doctor">doctor</Pill>)
  const pill = screen.getByText('doctor')
  expect(pill.dataset.tone).toBe('doctor')
  expect(pill.className).toMatch(/emerald/)
})

test('protect beat lights only the doctor and marks the protected seat', () => {
  renderCircle(
    makePlayers(),
    beat({
      kind: 'protect',
      palette: 'night',
      actor_id: 3,
      target_id: 4,
      text: 'The doctor protects P4.',
    })
  )
  expect(dimmed(3)).toBe('false')
  for (const id of [1, 2, 4, 5, 6]) expect(dimmed(id)).toBe('true')
  expect(within(screen.getByTestId('seat-4')).getByTestId('shield-mark')).toBeInTheDocument()
  expect(screen.queryAllByTestId('shield-mark')).toHaveLength(1)
})

test('lovers always carry a heart marker', () => {
  renderCircle(makePlayers(), beat({}))
  expect(within(screen.getByTestId('seat-4')).getByTestId('heart-mark')).toBeInTheDocument()
  expect(within(screen.getByTestId('seat-5')).getByTestId('heart-mark')).toBeInTheDocument()
  expect(screen.queryAllByTestId('heart-mark')).toHaveLength(2)
})

test('sidebar says who a lover is in love with', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ text: '' }) })
  )
  const players = makePlayers()
  await act(async () => {
    render(<PlayerSidebar gameId={1} player={players[3]} alive seq={1} players={players} />)
  })
  expect(screen.getByText('In love with P5')).toBeInTheDocument()
})

test('lover_message lights both lovers and shows the bubble', () => {
  renderCircle(
    makePlayers(),
    beat({ kind: 'lover_message', palette: 'night', actor_id: 4, text: 'Meet me at dawn' })
  )
  expect(dimmed(4)).toBe('false')
  expect(dimmed(5)).toBe('false')
  for (const id of [1, 2, 3, 6]) expect(dimmed(id)).toBe('true')
  expect(screen.getByRole('note')).toHaveTextContent('Meet me at dawn')
  expect(screen.getByTestId('seat-4').dataset.speaker).toBe('true')
})

test('wolf night beats still light the wolves', () => {
  renderCircle(makePlayers(), beat({ kind: 'phase_change', palette: 'night' }))
  expect(dimmed(1)).toBe('false')
  expect(dimmed(2)).toBe('true')
})

test('peaceful_night shows its text and nobody fades', () => {
  renderCircle(makePlayers(), beat({ kind: 'peaceful_night', text: 'Nobody died last night.' }))
  expect(screen.getByText('Nobody died last night.')).toBeInTheDocument()
  for (let id = 1; id <= 6; id++) {
    expect(screen.getByTestId(`seat-${id}`).dataset.state).toBe('alive')
    expect(dimmed(id)).toBe('false')
  }
})

test('heartbreak fades the victim with a role badge', () => {
  renderCircle(
    makePlayers(),
    beat({
      kind: 'heartbreak',
      victim_id: 5,
      role: 'villager',
      text: 'P5 died of a broken heart.',
    }),
    [1, 2, 3, 6]
  )
  const seat = screen.getByTestId('seat-5')
  expect(seat.dataset.state).toBe('dead')
  expect(within(seat).getByText('villager')).toBeInTheDocument()
  expect(screen.getByText('P5 died of a broken heart.')).toBeInTheDocument()
})

test('lovers winner text', () => {
  expect(winnerText('lovers')).toBe('The lovers win')
})

test('a 12-player game renders 12 seats with smaller seats', () => {
  renderCircle(makePlayers(12), beat({}))
  for (let id = 1; id <= 12; id++) expect(screen.getByTestId(`seat-${id}`)).toBeInTheDocument()
  expect(screen.getByTestId('seat-1').dataset.compact).toBe('true')
})

test('a small game keeps full-size seats', () => {
  renderCircle(makePlayers(7), beat({}))
  expect(screen.getByTestId('seat-1').dataset.compact).toBe('false')
})
