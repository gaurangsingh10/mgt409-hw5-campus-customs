import { useEffect } from 'react'

/** A short opening crawl (original text) the first time the desk opens each session. */
export function Crawl({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 21000)
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') onDone() }
    window.addEventListener('keydown', key)
    return () => { clearTimeout(t); window.removeEventListener('keydown', key) }
  }, [onDone])

  return (
    <div className="crawl" role="dialog" aria-label="Opening crawl" onClick={onDone}>
      <div className="crawl__stars" />
      <p className="crawl__intro">Not so long ago, on a campus not so far away…</p>
      <div className="crawl__stage">
        <div className="crawl__text">
          <p className="crawl__episode">Episode 101</p>
          <h2>THE THREE TICKETS</h2>
          <p>It is a period of tight cash. A lone merch shop on Chapel Street holds out with $3,400 in its vault, one overdue invoice, and rent due in two days.</p>
          <p>Three requests have reached the desk: a student who needs a tee that is not on the shelf, a landlord who wants to be paid, and a club that wants twenty hoodies at a price it hasn't earned yet.</p>
          <p>A council of five agents stands ready to investigate. But they may only <em>propose</em>. Every payment, discount and message must carry the seal of a human at the desk…</p>
        </div>
      </div>
      <button className="crawl__skip" onClick={onDone}>Skip ▸</button>
    </div>
  )
}
