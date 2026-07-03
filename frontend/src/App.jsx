import { Routes, Route, NavLink } from 'react-router-dom'
import Home from './pages/Home'
import About from './pages/About'
import Banner from './components/Banner'
import BottomNav from './components/BottomNav'
import Footer from './components/Footer'

function App() {
  return (
    <div className="flex min-h-screen flex-col bg-[#faf5e4] pb-12 text-[#3d2b1f] lg:pb-0">
      <Banner />
      <header className="hidden lg:flex shrink-0 items-center border-b border-[#d4bc8a] p-1">
        <h1>
          <NavLink to="/">
            <img src="/assets/logo.png" alt="Tokenbury-on-Sea" className="h-28 w-auto" />
          </NavLink>
        </h1>
        <nav className="ml-auto pr-4">
          <NavLink
            to="/about"
            className={({ isActive }) =>
              `rounded-lg border border-[#d4bc8a] px-4 py-2 font-semibold transition-colors hover:bg-[#f0e6c8] ${
                isActive ? 'bg-[#f0e6c8]' : 'bg-[#faf5e4]'
              }`
            }
          >
            About
          </NavLink>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
      </Routes>
      <Footer />
      <BottomNav />
    </div>
  )
}

export default App
