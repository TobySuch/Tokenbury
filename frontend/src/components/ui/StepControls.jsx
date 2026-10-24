import Button from './Button'
import Panel from './Panel'

export default function StepControls({
  index,
  count,
  label,
  isLive,
  onPrev,
  onNext,
  onScrub,
  onLive,
  canPrev = index > 0,
  canNext = !isLive && index < count - 1,
  leading = null,
  trailing = null,
  scrubLabel = 'Scrub through steps',
  prevLabel = 'Previous',
  nextLabel = 'Next',
  prevText = '←',
  nextText = '→',
  className = '',
}) {
  return (
    <Panel className={`flex flex-col gap-2 px-4 py-3 ${className}`.trim()}>
      <div className="flex items-center gap-2">
        {leading}
        <Button onClick={onPrev} disabled={!canPrev} aria-label={prevLabel}>
          {prevText}
        </Button>
        <span className="flex-1 text-center font-mono text-sm text-ink">{label}</span>
        <Button onClick={onNext} disabled={!canNext} aria-label={nextLabel}>
          {nextText}
        </Button>
        {trailing}
      </div>
      <div className="flex items-center gap-2">
        {count > 1 && (
          <input
            type="range"
            min={0}
            max={count - 1}
            value={index >= 0 ? index : 0}
            onChange={(e) => onScrub(parseInt(e.target.value, 10))}
            className="flex-1 cursor-pointer accent-ink"
            aria-label={scrubLabel}
          />
        )}
        <Button
          variant={isLive ? 'live' : 'default'}
          onClick={onLive}
          disabled={isLive}
          aria-label="Go to live"
        >
          ● LIVE
        </Button>
      </div>
    </Panel>
  )
}
