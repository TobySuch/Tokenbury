import { useState, useEffect } from 'react'
import { fetchBanner } from '../api/client'

function Banner() {
  const [banner, setBanner] = useState(null)

  useEffect(() => {
    fetchBanner().then(setBanner)
    const id = setInterval(() => {
      fetchBanner().then(setBanner)
    }, 30_000)
    return () => clearInterval(id)
  }, [])

  if (!banner) return null

  return (
    <div className="border-b border-[#d4bc8a] bg-[#f5edcf] px-4 py-2 text-center text-sm text-[#3d2b1f]">
      {banner.text}
    </div>
  )
}

export default Banner
