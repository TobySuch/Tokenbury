import { useState, useEffect } from 'react'

function App() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    fetch('/api/health/')
      .then((r) => r.json())
      .then(setStatus)
  }, [])

  return (
    <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Tokenbury-on-Sea</h1>
        {status ? (
          <p className="text-green-400">{status.message}</p>
        ) : (
          <p className="text-slate-400">Connecting...</p>
        )}
      </div>
    </div>
  )
}

export default App
