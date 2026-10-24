import { render, screen, fireEvent } from '@testing-library/react'
import Button from './Button'
import Pill from './Pill'
import Panel from './Panel'
import StepControls from './StepControls'

describe('Button', () => {
  test('forwards props and handles clicks', () => {
    const onClick = vi.fn()
    render(
      <Button onClick={onClick} aria-label="Go">
        x
      </Button>
    )
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
  test('can be disabled', () => {
    render(<Button disabled>x</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })
  test('merges extra className', () => {
    render(<Button className="extra">x</Button>)
    expect(screen.getByRole('button')).toHaveClass('extra')
  })
})

describe('Pill', () => {
  test('renders children', () => {
    render(<Pill>happy</Pill>)
    expect(screen.getByText('happy')).toBeInTheDocument()
  })
  test('applies tone variant', () => {
    render(<Pill tone="wolf">wolf</Pill>)
    expect(screen.getByText('wolf')).toHaveAttribute('data-tone', 'wolf')
  })
})

describe('Panel', () => {
  test('renders children and className', () => {
    render(<Panel className="mine">hello</Panel>)
    expect(screen.getByText('hello')).toHaveClass('mine')
  })
})

describe('StepControls', () => {
  const setup = (props = {}) => {
    const handlers = {
      onPrev: vi.fn(),
      onNext: vi.fn(),
      onScrub: vi.fn(),
      onLive: vi.fn(),
    }
    render(
      <StepControls
        index={1}
        count={5}
        label="Step 2 of 5"
        isLive={false}
        {...handlers}
        {...props}
      />
    )
    return handlers
  }
  test('renders the label and fires handlers', () => {
    const h = setup()
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    fireEvent.click(screen.getByRole('button', { name: 'Go to live' }))
    fireEvent.change(screen.getByRole('slider'), { target: { value: '3' } })
    expect(h.onPrev).toHaveBeenCalled()
    expect(h.onNext).toHaveBeenCalled()
    expect(h.onLive).toHaveBeenCalled()
    expect(h.onScrub).toHaveBeenCalledWith(3)
  })
  test('disables at the ends and when live', () => {
    setup({ index: 0, canPrev: false, isLive: true })
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Go to live' })).toBeDisabled()
  })
  test('renders leading and trailing slots', () => {
    setup({ leading: <i>lead</i>, trailing: <i>trail</i> })
    expect(screen.getByText('lead')).toBeInTheDocument()
    expect(screen.getByText('trail')).toBeInTheDocument()
  })
})
