import TownView from './components/town/TownView'

function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-white">
      <header className="p-4 border-b border-slate-700">
        <h1 className="text-2xl font-bold">Tokenbury-on-Sea</h1>
      </header>
      <main className="p-4 flex justify-center">
        <TownView />
      </main>
    </div>
  )
}

export default App
