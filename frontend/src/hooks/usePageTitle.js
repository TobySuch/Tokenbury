import { useEffect } from 'react'

// Caddy renders the right <title> on first load; this keeps it right as the
// SPA navigates between routes without reloading index.html.
export default function usePageTitle(title) {
  useEffect(() => {
    document.title = title
  }, [title])
}
