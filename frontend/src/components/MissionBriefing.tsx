import { useEffect, useState } from 'react'
import type { RunResult, Ticket } from '../api'

interface Props {
  ticket: Ticket
  runningHere: boolean
  busyElsewhere: number | null
  startedAt: number | null
  usage: { input: number; output: number; requests: number }
  lastResult: RunResult | null
  onEngage: () => void
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(id)
  }, [])
  const s = Math.max(0, Math.floor((now - since) / 1000))
  return <>{Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}</>
}

export function MissionBriefing({ ticket, runningHere, busyElsewhere, startedAt, usage, lastResult, onEngage }: Props) {
  const original = (ticket.notes ?? '').split('\n')[0]
  const resolved = ticket.state === 'resolved'
  const disabled = resolved || runningHere || busyElsewhere !== null

  let cta = 'Dispatch the Council'
  if (runningHere) cta = 'Council in session…'
  else if (resolved) cta = 'Mission complete'
  else if (busyElsewhere !== null) cta = `Council busy on #${busyElsewhere}`

  return (
    <section className={`panel briefing ${runningHere ? 'briefing--live' : ''} ${resolved ? 'briefing--done' : ''}`} aria-label="Mission briefing">
      <div className="briefing__main">
        <div className="briefing__eyebrow">Mission #{ticket.id} · {ticket.type.replace('_', ' ')}</div>
        <h2 className="briefing__title">{ticket.subject}</h2>
        <blockquote className="briefing__quote">“{original}” <cite>— {ticket.requester}</cite></blockquote>
        <dl className="briefing__facts">
          {ticket.sku && <><dt>Item</dt><dd><code>{ticket.sku}</code> · size {ticket.size} · ×{ticket.qty}</dd></>}
          {ticket.invoice_id != null && <><dt>Linked invoice</dt><dd>#{ticket.invoice_id}</dd></>}
          {ticket.lease_id != null && <><dt>Linked lease</dt><dd>#{ticket.lease_id}</dd></>}
          <dt>Received</dt><dd>{ticket.created_at.replace('T', ' ').slice(0, 16)}</dd>
        </dl>
      </div>

      <div className="briefing__side">
        <button className="engage" onClick={onEngage} disabled={disabled}>
          <span className="engage__glow" aria-hidden />
          <span className="engage__text">{cta}</span>
        </button>
        {runningHere && startedAt !== null && (
          <div className="hyperdrive" role="status">
            <div className="hyperdrive__bar"><i /></div>
            <div className="hyperdrive__stats">
              <span>T+<Elapsed since={startedAt} /></span>
              <span>{usage.requests} model calls</span>
              <span>{(usage.input + usage.output).toLocaleString()} tokens</span>
            </div>
          </div>
        )}
        {!runningHere && lastResult && (
          <div className={`outcome ${lastResult.ok ? 'outcome--ok' : 'outcome--bad'}`}>
            {lastResult.ok
              ? <>Run complete · {lastResult.usage.requests} calls · {((lastResult.usage.input_tokens ?? 0) + (lastResult.usage.output_tokens ?? 0)).toLocaleString()} tokens</>
              : <>Run failed: {lastResult.error}</>}
          </div>
        )}
        {resolved && !runningHere && <p className="briefing__note">Resolved. Anything the council asked for is waiting in <b>Awaiting your seal</b>.</p>}
      </div>
    </section>
  )
}
