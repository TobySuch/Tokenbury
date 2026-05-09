import TownView from './components/town/TownView'

function App() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-900 text-white">
      <header className="shrink-0 border-b border-slate-700 p-4">
        <h1 className="text-2xl font-bold">Tokenbury-on-Sea</h1>
      </header>
      <main className="flex flex-1 overflow-hidden">
        <div className="min-w-0 flex-1 lg:w-3/4 lg:flex-none">
          <TownView />
        </div>
        <aside className="hidden border-l border-slate-700 p-4 lg:block lg:w-1/4">
          {/* sidebar */}
        </aside>
      </main>
    </div>
  )
}

export default App
