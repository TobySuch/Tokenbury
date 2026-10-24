import { useState, useEffect } from 'react'
import { fetchBanner } from '../api/client'

function Banner({ site = 'town' }) {
  const [banner, setBanner] = useState(null)

  useEffect(() => {
    let cancelled = false
    const load = () =>
      fetchBanner(site).then((b) => {
        if (!cancelled) setBanner(b)
      })
    load()
    const id = setInterval(load, 30_000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [site])

  if (!banner) return null

  return (
    <div className="border-b border-[#d4bc8a] bg-[#f5edcf] px-4 py-2 text-center text-sm text-[#3d2b1f]">
      {banner.text}
    </div>
  )
}

export default Banner
