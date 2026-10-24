import Button from '../ui/Button'
import StepControls from '../ui/StepControls'

function formatTickTime(inGameTime) {
  if (!inGameTime) return '—'
  const d = new Date(inGameTime)
  const day = d.toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })
  const date = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
  const time = d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  })
  return `${day} ${date} · ${time}`
}

export default function TimelineScrubber({
  days = [],
  currentDay,
  dayTicks = [],
  currentIndex,
  isLive,
  onPrevTick,
  onNextTick,
  onPrevDay,
  onNextDay,
  onGoLive,
  onScrubTick,
}) {
  const currentDayIndex = days.indexOf(currentDay)
  const hasPrevDay = currentDayIndex > 0
  const hasNextDay = currentDayIndex < days.length - 1
  const currentTick = dayTicks[currentIndex]

  return (
    <StepControls
      className="mt-3"
      index={currentIndex}
      count={dayTicks.length}
      label={formatTickTime(currentTick?.in_game_time)}
      isLive={isLive}
      onPrev={onPrevTick}
      onNext={onNextTick}
      onScrub={onScrubTick}
      onLive={onGoLive}
      canPrev={!(currentIndex <= 0 && !hasPrevDay)}
      canNext={!isLive}
      prevLabel="Previous tick"
      nextLabel="Next tick"
      scrubLabel="Scrub through ticks"
      leading={
        <Button onClick={onPrevDay} disabled={!hasPrevDay} aria-label="Previous day">
          ◄
        </Button>
      }
      trailing={
        <Button onClick={onNextDay} disabled={isLive && !hasNextDay} aria-label="Next day">
          ►
        </Button>
      }
    />
  )
}
