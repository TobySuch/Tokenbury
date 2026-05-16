import { NavLink } from 'react-router-dom'

function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex lg:hidden border-t border-[#d4bc8a] bg-[#faf5e4]">
      <NavLink
        to="/"
        end
        className={({ isActive }) =>
          `flex flex-1 items-center justify-center py-3 text-sm font-semibold transition-colors ${
            isActive ? 'bg-[#f0e6c8] text-[#3d2b1f]' : 'text-[#7a6248] hover:bg-[#f0e6c8]'
          }`
        }
      >
        Town
      </NavLink>
      <NavLink
        to="/about"
        className={({ isActive }) =>
          `flex flex-1 items-center justify-center py-3 text-sm font-semibold transition-colors ${
            isActive ? 'bg-[#f0e6c8] text-[#3d2b1f]' : 'text-[#7a6248] hover:bg-[#f0e6c8]'
          }`
        }
      >
        About
      </NavLink>
    </nav>
  )
}

export default BottomNav
