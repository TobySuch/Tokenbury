import { useState, useEffect, useRef, useCallback } from 'react'
import TownView from './components/town/TownView'
import AgentPanel from './components/agents/AgentPanel'
import TimelineScrubber from './components/timeline/TimelineScrubber'
import {
  fetchLocations,
  fetchLatestTick,
  fetchTicks,
  fetchTickDays,
  fetchTickById,
} from './api/client'

function tickToDay(inGameTime) {
  return inGameTime ? inGameTime.substring(0, 10) : null
}

function App() {
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [locations, setLocations] = useState([])
  const [days, setDays] = useState([])
  const [currentDay, setCurrentDay] = useState(null)
  const [dayTicks, setDayTicks] = useState([])
  const [latestTickData, setLatestTickData] = useState(null)
  const [historicalTickData, setHistoricalTickData] = useState(null)
  const [selectedTickId, setSelectedTickId] = useState(null)

  const lastTickIdRef = useRef(null)
  const isLiveRef = useRef(true)
  const liveDayRef = useRef(null)
  const handlePrevTickRef = useRef(null)
  const handleNextTickRef = useRef(null)

  const isLive = selectedTickId === null
  const tickData = isLive ? latestTickData : historicalTickData
  const currentIndex = isLive
    ? dayTicks.length - 1
    : dayTicks.findIndex((t) => t.id === selectedTickId)
  const currentDayIndex = days.indexOf(currentDay)
  const hasPrevDay = currentDayIndex > 0
  const canGoPrev = currentIndex > 0 || hasPrevDay
  const canGoNext = !isLive

  useEffect(() => {
    isLiveRef.current = isLive
  }, [isLive])

  useEffect(() => {
    Promise.all([fetchLocations(), fetchTickDays(), fetchLatestTick()]).then(
      ([locs, daysData, latest]) => {
        setLocations(locs)
        setDays(daysData)
        if (latest) {
          setLatestTickData(latest)
          lastTickIdRef.current = latest.id
          const liveDay = tickToDay(latest.in_game_time)
          liveDayRef.current = liveDay
          setCurrentDay(liveDay)
          fetchTicks(liveDay).then((ticks) => setDayTicks([...ticks].reverse()))
        }
      }
    )
  }, [])

  useEffect(() => {
    const id = setInterval(() => {
      fetchLatestTick(lastTickIdRef.current).then((tick) => {
        if (!tick) return
        lastTickIdRef.current = tick.id
        setLatestTickData(tick)
        const newDay = tickToDay(tick.in_game_time)
        setDays((prev) => (prev.includes(newDay) ? prev : [...prev, newDay]))
        liveDayRef.current = newDay
        if (isLiveRef.current) {
          setCurrentDay((prev) => {
            if (prev === newDay) {
              setDayTicks((prevTicks) => {
                if (prevTicks.some((t) => t.id === tick.id)) return prevTicks
                return [...prevTicks, { id: tick.id, in_game_time: tick.in_game_time }]
              })
              return prev
            }
            // New day rolled over
            setDayTicks([{ id: tick.id, in_game_time: tick.in_game_time }])
            return newDay
          })
        }
      })
    }, 30_000)
    return () => clearInterval(id)
  }, [])

  const loadDay = useCallback(async (day) => {
    const ticks = await fetchTicks(day)
    const ordered = [...ticks].reverse()
    setCurrentDay(day)
    setDayTicks(ordered)
    return ordered
  }, [])

  async function goToTick(tick) {
    const isLastOfLiveDay = tick.id === latestTickData?.id
    if (isLastOfLiveDay) {
      setSelectedTickId(null)
      return
    }
    setSelectedTickId(tick.id)
    const data = await fetchTickById(tick.id)
    setHistoricalTickData(data)
  }

  async function handleScrubTick(index) {
    const ordered = dayTicks
    if (!ordered[index]) return
    await goToTick(ordered[index])
  }

  async function handlePrevTick() {
    if (currentIndex > 0) {
      await goToTick(dayTicks[currentIndex - 1])
      return
    }
    const prevDayIndex = days.indexOf(currentDay) - 1
    if (prevDayIndex < 0) return
    const ordered = await loadDay(days[prevDayIndex])
    if (ordered.length > 0) await goToTick(ordered[ordered.length - 1])
  }

  async function handleNextTick() {
    const isLastInDay = currentIndex >= dayTicks.length - 1
    if (!isLastInDay) {
      await goToTick(dayTicks[currentIndex + 1])
      return
    }
    const nextDayIndex = days.indexOf(currentDay) + 1
    if (nextDayIndex >= days.length) {
      // No next day — go live
      handleGoLive()
      return
    }
    const ordered = await loadDay(days[nextDayIndex])
    if (ordered.length > 0) await goToTick(ordered[0])
  }

  async function handlePrevDay() {
    const prevDayIndex = days.indexOf(currentDay) - 1
    if (prevDayIndex < 0) return
    const ordered = await loadDay(days[prevDayIndex])
    if (ordered.length > 0) await goToTick(ordered[0])
  }

  async function handleNextDay() {
    const nextDayIndex = days.indexOf(currentDay) + 1
    if (nextDayIndex >= days.length) {
      handleGoLive()
      return
    }
    const ordered = await loadDay(days[nextDayIndex])
    if (ordered.length > 0) await goToTick(ordered[0])
  }

  async function handleGoLive() {
    setSelectedTickId(null)
    const liveDay = liveDayRef.current
    if (liveDay && liveDay !== currentDay) {
      const ordered = await loadDay(liveDay)
      setDayTicks(ordered)
    }
  }

  // Keep refs current so the keydown listener always calls the latest handler
  // without needing to re-subscribe on every render.
  handlePrevTickRef.current = handlePrevTick
  handleNextTickRef.current = handleNextTick

  useEffect(() => {
    function onKeyDown(e) {
      if (e.target.tagName === 'INPUT') return // let range slider handle its own arrows
      if (e.key === 'ArrowLeft') handlePrevTickRef.current()
      if (e.key === 'ArrowRight') handleNextTickRef.current()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const BTN =
    'flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg border border-[#d4bc8a] bg-[#faf5e4] px-3 text-[#3d2b1f] font-semibold transition-colors hover:bg-[#f0e6c8] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer select-none'

  return (
    <div className="flex min-h-screen flex-col bg-[#faf5e4] text-[#3d2b1f]">
      <header className="hidden lg:block shrink-0 border-b border-[#d4bc8a] p-1">
        <h1>
          <img src="/assets/logo.png" alt="Tokenbury-on-Sea" className="h-28 w-auto" />
        </h1>
      </header>
      <main className="flex flex-1 flex-col overflow-auto lg:flex-row lg:overflow-hidden">
        <div className="min-w-0 p-4 lg:w-2/3 lg:flex-none">
          {/* Portrait mini nav — above map, small portrait screens only */}
          <div className="hidden max-lg:portrait:flex items-center gap-3 pb-2">
            <img src="/assets/logo.png" alt="Tokenbury-on-Sea" className="h-8 w-auto" />
            <div className="ml-auto flex gap-3">
              <button
                className={BTN}
                onClick={handlePrevTick}
                disabled={!canGoPrev}
                aria-label="Previous tick"
              >
                ←
              </button>
              <button
                className={BTN}
                onClick={handleNextTick}
                disabled={!canGoNext}
                aria-label="Next tick"
              >
                →
              </button>
            </div>
          </div>

          {/* Map row — flex in small landscape so buttons sit left of map */}
          <div className="max-lg:landscape:flex max-lg:landscape:items-center max-lg:landscape:gap-2">
            {/* Landscape mini nav — logo + stacked buttons left of map, small landscape only */}
            <div className="hidden max-lg:landscape:flex flex-col items-center gap-2">
              <img src="/assets/logo.png" alt="Tokenbury-on-Sea" className="h-8 w-auto" />
              <button
                className={BTN}
                onClick={handlePrevTick}
                disabled={!canGoPrev}
                aria-label="Previous tick"
              >
                ←
              </button>
              <button
                className={BTN}
                onClick={handleNextTick}
                disabled={!canGoNext}
                aria-label="Next tick"
              >
                →
              </button>
            </div>
            <div className="max-lg:landscape:flex-1 max-lg:landscape:min-w-0">
              <TownView
                locations={locations}
                tickData={tickData}
                onAgentChange={setSelectedAgent}
                className="max-lg:landscape:mx-0"
              />
            </div>
          </div>

          {/* Full scrubber — large screens only */}
          <div className="hidden lg:block">
            <TimelineScrubber
              days={days}
              currentDay={currentDay}
              dayTicks={dayTicks}
              currentIndex={currentIndex}
              isLive={isLive}
              onPrevTick={handlePrevTick}
              onNextTick={handleNextTick}
              onPrevDay={handlePrevDay}
              onNextDay={handleNextDay}
              onGoLive={handleGoLive}
              onScrubTick={handleScrubTick}
            />
          </div>
        </div>
        <aside className="border-t border-[#d4bc8a] p-4 lg:w-1/3 lg:border-l lg:border-t-0">
          <AgentPanel agent={selectedAgent} />
        </aside>
      </main>
    </div>
  )
}

export default App
