function Footer() {
  return (
    <footer className="shrink-0 border-t border-[#d4bc8a] px-4 py-3 text-xs text-[#7a6248]">
      <p>
        Created by{' '}
        <a href="https://www.tobysuch.uk" target="_blank" className="hover:underline">
          Toby Such
        </a>{' '}
        · © 2026 Toby Such · Code available under the{' '}
        <a
          href="https://github.com/TobySuch/Tokenbury/blob/main/LICENSE"
          target="_blank"
          className="hover:underline"
        >
          GNU GPL v3
        </a>{' '}
        ·{' '}
        <a href="https://github.com/TobySuch/Tokenbury" target="_blank" className="hover:underline">
          GitHub
        </a>
      </p>
      <p className="mt-1">Game assets © 2026 Toby Such · All rights reserved</p>
    </footer>
  )
}

export default Footer
