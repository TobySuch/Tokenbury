export default function Panel({ className = '', children, ...props }) {
  return (
    <div
      className={`rounded-xl border border-rule bg-paper transition-colors duration-500 ${className}`.trim()}
      {...props}
    >
      {children}
    </div>
  )
}
