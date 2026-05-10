import TownView from './components/town/TownView'

function App() {
  return (
    <div className="flex min-h-screen flex-col bg-[#faf5e4] text-[#3d2b1f]">
      <header className="shrink-0 border-b border-[#d4bc8a] p-4">
        <h1 className="text-2xl font-bold italic">Tokenbury-on-Sea</h1>
      </header>
      <main className="flex flex-1 overflow-hidden">
        <div className="min-w-0 flex-1 p-4 lg:w-3/4 lg:flex-none">
          <TownView />
        </div>
        <aside className="hidden border-l border-[#d4bc8a] p-4 lg:block lg:w-1/4">
          {/* sidebar */}
        </aside>
      </main>
    </div>
  )
}

export default App
