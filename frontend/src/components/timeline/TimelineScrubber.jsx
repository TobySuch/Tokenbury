function formatDay(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr + 'T00:00:00Z')
  return d.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

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

const BTN =
  'flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg border border-[#d4bc8a] bg-[#faf5e4] px-3 text-[#3d2b1f] font-semibold transition-colors hover:bg-[#f0e6c8] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer select-none'

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
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-[#d4bc8a] bg-[#faf5e4] px-4 py-3">
      {/* Day picker row */}
      <div className="flex items-center gap-2">
        <button
          className={BTN}
          onClick={onPrevDay}
          disabled={!hasPrevDay}
          aria-label="Previous day"
        >
          ◄
        </button>
        <span className="flex-1 text-center font-mono text-sm text-[#3d2b1f]">
          {formatDay(currentDay)}
        </span>
        <button
          className={BTN}
          onClick={onNextDay}
          disabled={isLive && !hasNextDay}
          aria-label="Next day"
        >
          ►
        </button>
      </div>

      {/* Tick nav row */}
      <div className="flex items-center gap-2">
        <button
          className={BTN}
          onClick={onPrevTick}
          disabled={currentIndex <= 0 && !hasPrevDay}
          aria-label="Previous tick"
        >
          ←
        </button>
        <span className="flex-1 text-center font-mono text-sm text-[#3d2b1f]">
          {formatTickTime(currentTick?.in_game_time)}
        </span>
        <button className={BTN} onClick={onNextTick} disabled={isLive} aria-label="Next tick">
          →
        </button>
        <button
          className={`${BTN} ${isLive ? 'border-green-600 bg-green-600 text-white hover:bg-green-700' : ''}`}
          onClick={onGoLive}
          disabled={isLive}
          aria-label="Go to live"
        >
          ● LIVE
        </button>
      </div>

      {/* Range slider */}
      {dayTicks.length > 1 && (
        <input
          type="range"
          min={0}
          max={dayTicks.length - 1}
          value={currentIndex >= 0 ? currentIndex : 0}
          onChange={(e) => onScrubTick(parseInt(e.target.value, 10))}
          className="w-full cursor-pointer accent-[#3d2b1f]"
          aria-label="Scrub through ticks"
        />
      )}
    </div>
  )
}
