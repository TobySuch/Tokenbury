import { render, screen, act, fireEvent } from '@testing-library/react'
import PlayerCircle from './PlayerCircle'
import PlayerSidebar from './PlayerSidebar'
import SpeechBubble from './SpeechBubble'

const LONG = 'A very long speech. '.repeat(40).trim()

const player = (id, extra = {}) => ({
  id,
  name: `P${id}`,
  seat: id,
  avatar_url: `/media/werewolf/avatars/p${id}.png`,
  role: 'villager',
  wolf_label: null,
  alive: true,
  ...extra,
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('speech bubble shows the full text in a scrollable area', () => {
  render(<SpeechBubble text={LONG} x={50} y={20} />)
  const scroller = screen.getByTestId('speech-bubble-scroll')
  expect(scroller).toHaveTextContent(LONG)
  expect(scroller.className).toMatch(/overflow-y-auto/)
  expect(scroller.className).toMatch(/max-h-/)
  expect(scroller.className).not.toMatch(/line-clamp/)
})

test('clicking inside a speech bubble does not bubble up to the seat', () => {
  const onClick = vi.fn()
  render(
    <div onClick={onClick}>
      <SpeechBubble text={LONG} x={50} y={20} />
    </div>
  )
  fireEvent.click(screen.getByTestId('speech-bubble-scroll'))
  expect(onClick).not.toHaveBeenCalled()
})

test('sidebar notes scroll instead of growing the page', async () => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ player_id: 1, version: 1, text: LONG, at_seq: 3 }),
    })
  )
  await act(async () => {
    render(<PlayerSidebar gameId={7} player={player(1)} alive seq={3} />)
  })
  const notes = screen.getByTestId('player-notes')
  expect(notes).toHaveTextContent(LONG)
  expect(notes.className).toMatch(/overflow-y-auto/)
  expect(notes.className).toMatch(/max-h-/)
})

test('avatars show the whole sprite rather than cropping it into a circle', () => {
  const players = [1, 2, 3].map((id) => player(id))
  const { container } = render(
    <PlayerCircle
      players={players}
      beat={null}
      aliveIds={new Set([1, 2, 3])}
      hoveredId={null}
      selectedId={null}
      onHover={() => {}}
      onSelect={() => {}}
    />
  )
  const imgs = container.querySelectorAll('img')
  expect(imgs).toHaveLength(3)
  for (const img of imgs) {
    expect(img.className).toMatch(/object-contain/)
    expect(img.className).not.toMatch(/object-cover|rounded-full/)
  }
})
