const TONES = {
  neutral: 'border-rule bg-chip text-ink',
  wolf: 'border-red-700 bg-red-700 text-white',
  seer: 'border-indigo-500 bg-indigo-500 text-white',
  doctor: 'border-emerald-600 bg-emerald-600 text-white',
  villager: 'border-rule bg-chip text-ink',
  live: 'border-green-600 bg-green-600 text-white',
}

export default function Pill({ tone = 'neutral', className = '', children, ...props }) {
  return (
    <span
      data-tone={tone}
      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${TONES[tone] ?? TONES.neutral} ${className}`.trim()}
      {...props}
    >
      {children}
    </span>
  )
}
