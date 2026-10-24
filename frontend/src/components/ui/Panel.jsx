export default function Panel({ className = '', children, ...props }) {
  return (
    <div className={`rounded-xl border border-rule bg-paper ${className}`.trim()} {...props}>
      {children}
    </div>
  )
}
