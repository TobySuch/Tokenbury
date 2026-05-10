import { useState } from 'react'
import TownView from './components/town/TownView'
import AgentPanel from './components/agents/AgentPanel'

function App() {
  const [selectedAgent, setSelectedAgent] = useState(null)

  return (
    <div className="flex min-h-screen flex-col bg-[#faf5e4] text-[#3d2b1f]">
      <header className="shrink-0 border-b border-[#d4bc8a] p-4">
        <h1 className="text-2xl font-bold italic">Tokenbury-on-Sea</h1>
      </header>
      <main className="flex flex-1 flex-col overflow-auto lg:flex-row lg:overflow-hidden">
        <div className="min-w-0 p-4 lg:w-3/4 lg:flex-none">
          <TownView onAgentChange={setSelectedAgent} />
        </div>
        <aside className="border-t border-[#d4bc8a] p-4 lg:w-1/4 lg:border-l lg:border-t-0">
          <AgentPanel agent={selectedAgent} />
        </aside>
      </main>
    </div>
  )
}

export default App
