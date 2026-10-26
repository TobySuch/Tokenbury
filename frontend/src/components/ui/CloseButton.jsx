export default function CloseButton({ className = '', label = 'Close', ...props }) {
  return (
    <button
      type="button"
      aria-label={label}
      className={`flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-paper-hover hover:text-ink ${className}`.trim()}
      {...props}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5" fill="none">
        <path
          d="M6 6l12 12M18 6L6 18"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </button>
  )
}
