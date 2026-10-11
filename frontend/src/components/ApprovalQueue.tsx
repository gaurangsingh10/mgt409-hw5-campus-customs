import { useState } from 'react'
import { AGENTS, AgentGlyph, KIND_LABEL } from '../agents'
import { MONEY_KINDS, usd, type Approval } from '../api'

interface Props {
  approvals: Approval[]
  ticketId: number | null
  balance: number | null
  floor: number
  busyId: number | null
  onDecide: (a: Approval, decision: 'approve' | 'reject', note: string) => void
}

function Seal({ a, balance, floor, busy, onDecide }: { a: Approval; balance: number | null; floor: number; busy: boolean; onDecide: Props['onDecide'] }) {
  const money = MONEY_KINDS.includes(a.kind)
  const after = money && balance != null && a.amount != null ? balance - a.amount : null
  const overdraw = after != null && after < 0
  const underFloor = after != null && after >= 0 && after < floor
  const [note, setNote] = useState('')
  return (
    <article className={`seal seal--${a.status} ${money ? 'seal--money' : ''}`}>
      <header className="seal__head">
        <span className={`agent-ink agent-ink--${a.requested_by}`}><AgentGlyph agent={a.requested_by} size={16} /> {AGENTS[a.requested_by]?.title}</span>
        <span className="seal__id">#{a.id} · ticket {a.ticket_id}</span>
      </header>
      <div className="seal__kind">{KIND_LABEL[a.kind]}</div>
      {a.amount != null && (
        <div className="seal__amount">
          {a.kind === 'price_override' && a.unit_price != null ? <>{a.qty} × {usd(a.unit_price)} = <b>{usd(a.amount)}</b></> : <b>{usd(a.amount)}</b>}
        </div>
      )}
      <p className="seal__summary">{a.summary}</p>
      {a.message && (
        <details className="seal__letter" open={a.status === 'pending'}>
          <summary>Draft message</summary>
          <p>{a.message}</p>
        </details>
      )}
      {a.status === 'pending' ? (
        <>
          {money && after != null && (
            <div className={`seal__after ${overdraw ? 'is-bad' : underFloor ? 'is-warn' : ''}`}>
              Checking after: <b>{usd(after)}</b>
              {overdraw && ' · not enough cash'}
              {underFloor && ` · below ${usd(floor)} floor`}
            </div>
          )}
          <input
            className="seal__note"
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Note for the record (optional)"
            aria-label={`Decision note for request ${a.id}`}
          />
          <div className="seal__actions">
            <button className="btn btn--approve" disabled={busy || overdraw} onClick={() => onDecide(a, 'approve', note)}>
              {busy ? 'Sealing…' : money ? 'Approve & pay' : 'Approve'}
            </button>
            <button className="btn btn--reject" disabled={busy} onClick={() => onDecide(a, 'reject', note)}>Reject</button>
          </div>
        </>
      ) : (
        <div className="seal__decided">
          {a.status === 'approved' ? '✔ Approved' : '✕ Rejected'} by <b>{a.decided_by}</b>
          {a.decision_note ? <> · “{a.decision_note}”</> : null}
        </div>
      )}
    </article>
  )
}

export function ApprovalQueue({ approvals, ticketId, balance, floor, busyId, onDecide }: Props) {
  const [scope, setScope] = useState<'ticket' | 'all'>('ticket')
  const shown = approvals
    .filter(a => scope === 'all' || a.ticket_id === ticketId)
    .sort((x, y) => (x.status === 'pending' ? 0 : 1) - (y.status === 'pending' ? 0 : 1) || x.id - y.id)
  const pending = shown.filter(a => a.status === 'pending').length
  return (
    <section className="panel queue" aria-label="Approvals">
      <div className="panel__head">
        <h2>Awaiting Your Seal</h2>
        <div className="seg">
          <button aria-pressed={scope === 'ticket'} onClick={() => setScope('ticket')}>This ticket</button>
          <button aria-pressed={scope === 'all'} onClick={() => setScope('all')}>All</button>
        </div>
      </div>
      <p className="muted queue__hint">
        Agents only <i>propose</i>. Nothing is paid, discounted, ordered or sent until you approve it here.
        {pending > 0 && <> <b>{pending}</b> waiting.</>}
      </p>
      {!shown.length && <p className="feed__empty">Nothing to approve {scope === 'ticket' ? 'on this ticket' : ''} yet.</p>}
      <div className="queue__list">
        {shown.map(a => <Seal key={a.id} a={a} balance={balance} floor={floor} busy={busyId === a.id} onDecide={onDecide} />)}
      </div>
    </section>
  )
}
