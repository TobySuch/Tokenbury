import { renderHook } from '@testing-library/react'
import usePageTitle from './usePageTitle'

test('sets the document title and updates it when the title changes', () => {
  const { rerender } = renderHook(({ title }) => usePageTitle(title), {
    initialProps: { title: 'First' },
  })
  expect(document.title).toBe('First')
  rerender({ title: 'Second' })
  expect(document.title).toBe('Second')
})
