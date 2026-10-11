import type { Ticket } from '../api'

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_on_stock: 'Waiting on stock',
  awaiting_approval: 'Awaiting approval',
  resolved: 'Resolved',
}

interface Props {
  tickets: Ticket[]
  selected: number | null
  running: number | null
  justResolved: Set<number>
  onSelect: (id: number) => void
}

export function TicketBoard({ tickets, selected, running, justResolved, onSelect }: Props) {
  const resolved = tickets.filter(t => t.state === 'resolved').length
  return (
    <section className="panel board" aria-label="Mission board">
      <div className="panel__head">
        <h2>Mission Board</h2>
        <span className="panel__meta">{resolved}/{tickets.length} resolved</span>
      </div>
      <div className="board__progress" aria-hidden>
        {tickets.map(t => <i key={t.id} className={t.state === 'resolved' ? 'done' : t.id === running ? 'live' : ''} />)}
      </div>
      <ul className="board__list">
        {tickets.map(t => {
          const isRunning = running === t.id
          const cls = [
            'holocard',
            t.id === selected && 'holocard--selected',
            t.state === 'resolved' && 'holocard--resolved',
            isRunning && 'holocard--running',
          ].filter(Boolean).join(' ')
          return (
            <li key={t.id}>
              <button className={cls} onClick={() => onSelect(t.id)} aria-pressed={t.id === selected}>
                <div className="holocard__top">
                  <span className="holocard__id">#{t.id}</span>
                  <span className="holocard__type">{TYPE_LABEL[t.type] ?? t.type}</span>
                </div>
                <div className="holocard__subject">{t.subject}</div>
                <div className="holocard__from">from {t.requester}</div>
                <div className="holocard__foot">
                  <span className={`pill pill--${isRunning ? 'running' : t.status}`}>
                    {isRunning ? 'Council in session' : STATUS_LABEL[t.status] ?? t.status}
                  </span>
                  {t.pending_approvals > 0 && <span className="holocard__seals">{t.pending_approvals} to approve</span>}
                </div>
                {t.state === 'resolved' && (
                  <span className={`stamp ${justResolved.has(t.id) ? 'stamp--fresh' : ''}`} aria-label="Resolved">Resolved</span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
