import { renderHook, act } from '@testing-library/react'
import { useBeats, POLL_MS } from './useBeats'
import * as api from './api'

vi.mock('./api')

const b = (index) => ({ index, kind: 'speech' })

afterEach(() => {
  vi.useRealTimers()
})

test('does one final beats fetch when the game stops being active', async () => {
  vi.useFakeTimers()
  api.fetchGame
    .mockResolvedValueOnce({ id: 1, status: 'active' })
    .mockResolvedValue({ id: 1, status: 'completed' })
  // Initial load has beat 0. The poll's concurrent beats request misses the final
  // beat (race with the game finishing); the follow-up request sees it.
  api.fetchBeats.mockImplementation(async (_id, after) => {
    if (after == null) return [b(0)]
    return api.fetchBeats.mock.calls.filter((c) => c[1] === 0).length === 1 ? [] : [b(1)]
  })

  const { result } = renderHook(() => useBeats(1))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
  expect(result.current.beats).toHaveLength(1)

  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_MS)
  })
  expect(result.current.game.status).toBe('completed')
  expect(result.current.beats.map((x) => x.index)).toEqual([0, 1])

  const calls = api.fetchBeats.mock.calls.length
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_MS * 3)
  })
  expect(api.fetchBeats.mock.calls.length).toBe(calls)
})
