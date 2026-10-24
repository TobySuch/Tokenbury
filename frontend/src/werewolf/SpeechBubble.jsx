/** Speech bubble anchored to a seat; `x`/`y` are the seat's percentage position in the circle. */
export default function SpeechBubble({ text, x, y }) {
  const vertical = y < 50 ? 'top-full mt-2' : 'bottom-full mb-2'
  const horizontal = x < 35 ? 'left-0' : x > 65 ? 'right-0' : 'left-1/2 -translate-x-1/2'
  return (
    <div
      role="note"
      className={`absolute z-20 w-52 max-w-[70vw] rounded-2xl border border-rule bg-paper px-3 py-2 text-left text-sm italic leading-snug text-ink shadow-md ${vertical} ${horizontal}`}
    >
      <span className="line-clamp-6">{text}</span>
    </div>
  )
}
