const BASE =
  'flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg border px-3 font-semibold transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer select-none'

const VARIANTS = {
  default: 'border-rule bg-paper text-ink hover:bg-paper-hover',
  live: 'border-green-600 bg-green-600 text-white hover:bg-green-700',
}

export default function Button({
  variant = 'default',
  className = '',
  type = 'button',
  children,
  ...props
}) {
  return (
    <button
      type={type}
      className={`${BASE} ${VARIANTS[variant] ?? VARIANTS.default} ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  )
}
