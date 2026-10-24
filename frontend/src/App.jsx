import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Home from './pages/Home'
import About from './pages/About'
import WerewolfPage from './werewolf/WerewolfPage'
import WerewolfAbout from './werewolf/WerewolfAbout'
import Banner from './components/Banner'
import BottomNav from './components/BottomNav'
import Footer from './components/Footer'

// Smaller logo link to the sister site, shown beside the main logo.
function SiteLink({ to, label, logo, alt }) {
  return (
    <NavLink
      to={to}
      className="ml-4 flex items-center gap-2 rounded-lg px-2 py-1 text-sm font-semibold italic text-[#7a6248] transition-colors hover:bg-[#f0e6c8]"
    >
      <span>{label}</span>
      <img src={logo} alt={alt} className="h-16 w-auto" />
    </NavLink>
  )
}

function App() {
  const onWerewolf = useLocation().pathname.startsWith('/werewolf')
  return (
    <div className="flex min-h-screen flex-col bg-[#faf5e4] pb-12 text-[#3d2b1f] lg:pb-0">
      <Banner />
      <header className="hidden lg:flex shrink-0 items-center border-b border-[#d4bc8a] p-1">
        {onWerewolf ? (
          <>
            <h1>
              <NavLink to="/werewolf" end>
                <img
                  src="/assets/werewolf-logo.webp"
                  alt="Tokenbury Werewolf"
                  className="h-28 w-auto"
                />
              </NavLink>
            </h1>
            <SiteLink to="/" label="Back to:" logo="/assets/logo.webp" alt="Tokenbury-on-Sea" />
          </>
        ) : (
          <>
            <h1>
              <NavLink to="/">
                <img src="/assets/logo.webp" alt="Tokenbury-on-Sea" className="h-28 w-auto" />
              </NavLink>
            </h1>
            <SiteLink
              to="/werewolf"
              label="Try:"
              logo="/assets/werewolf-logo.webp"
              alt="Tokenbury Werewolf"
            />
          </>
        )}
        <nav className="ml-auto flex gap-2 pr-4">
          <NavLink
            to={onWerewolf ? '/werewolf/about' : '/about'}
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
        <Route path="/werewolf" element={<WerewolfPage />} />
        <Route path="/werewolf/about" element={<WerewolfAbout />} />
        <Route path="/werewolf/:gameId" element={<WerewolfPage />} />
      </Routes>
      <Footer />
      <BottomNav />
    </div>
  )
}

export default App
