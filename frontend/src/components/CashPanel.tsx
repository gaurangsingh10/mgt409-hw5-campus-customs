import { useEffect, useRef, useState } from 'react'
import { KIND_LABEL } from '../agents'
import { MONEY_KINDS, usd, type Approval, type Cash } from '../api'

/** Counts the balance up/down to its new value so a payment visibly drains the vault. */
function useTween(target: number | null, ms = 1100) {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    if (target == null) return
    if (from.current == null || document.hidden || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      from.current = target
      setShown(target)
      return
    }
    const start = performance.now()
    const a = from.current
    let raf = 0
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms)
      const ease = 1 - Math.pow(1 - k, 3)
      setShown(a + (target - a) * ease)
      if (k < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    // Browsers pause requestAnimationFrame in background tabs; never leave a stale balance on screen.
    const settle = setTimeout(() => { cancelAnimationFrame(raf); from.current = target; setShown(target) }, ms + 150)
    return () => { cancelAnimationFrame(raf); clearTimeout(settle) }
  }, [target, ms])
  return shown
}

export function CashPanel({ cash, approvals }: { cash: Cash | null; approvals: Approval[] }) {
  const balance = cash?.balance ?? null
  const shown = useTween(balance)
  const prev = useRef<number | null>(null)
  const [delta, setDelta] = useState<{ v: number; key: number } | null>(null)

  useEffect(() => {
    if (balance == null) return
    if (prev.current != null && balance !== prev.current) setDelta({ v: balance - prev.current, key: Date.now() })
    prev.current = balance
  }, [balance])

  const scale = Math.max(3400, balance ?? 0)
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / scale) * 100))}%`
  const ledger = approvals.filter(a => a.status === 'approved' && MONEY_KINDS.includes(a.kind))
  const floor = cash?.cash_floor ?? 500
  const low = balance != null && balance < floor

  return (
    <section className={`panel vault ${low ? 'vault--low' : ''}`} aria-label="Checking balance">
      <div className="panel__head">
        <h2>Treasury Vault</h2>
        <span className="panel__meta">checking · {cash?.as_of ?? '—'}</span>
      </div>
      <div className="vault__balance" aria-live="polite">
        <span className="vault__amount">{shown == null ? '—' : usd(Math.round(shown * 100) / 100)}</span>
        {delta && <span key={delta.key} className={`vault__delta ${delta.v < 0 ? 'neg' : 'pos'}`}>{delta.v < 0 ? '−' : '+'}{usd(Math.abs(delta.v))}</span>}
      </div>
      {cash && (
        <>
          <div className="gauge" aria-hidden>
            <div className="gauge__fill" style={{ width: pct(cash.balance) }} />
            <div className="gauge__proj" style={{ left: pct(Math.max(0, cash.cash_after_all_obligations)) }} title="After all obligations" />
            <div className="gauge__floor" style={{ left: pct(floor) }} />
          </div>
          <div className="gauge__legend">
            <span><i className="lg lg--floor" /> {usd(floor)} floor</span>
            <span><i className="lg lg--proj" /> after all bills: <b>{usd(cash.cash_after_all_obligations)}</b></span>
          </div>
          <dl className="vault__owed">
            <dt>Open invoices</dt><dd>{usd(cash.open_invoices_total)}</dd>
            <dt>Rent due ≤30 days</dt><dd>{usd(cash.rent_due_total)}</dd>
          </dl>
        </>
      )}
      <div className="ledger">
        <div className="ledger__title">Ledger</div>
        {!ledger.length && <p className="muted">No payments yet. Approved payments drop the balance here.</p>}
        {ledger.map(a => (
          <div key={a.id} className="ledger__row">
            <span>{KIND_LABEL[a.kind]} <small>#{a.id} · {a.decided_by}</small></span>
            <b>−{usd(a.amount)}</b>
          </div>
        ))}
      </div>
    </section>
  )
}
