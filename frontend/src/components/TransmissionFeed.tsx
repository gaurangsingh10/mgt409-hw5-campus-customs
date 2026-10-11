import { useEffect, useRef } from 'react'
import { AGENTS, AgentGlyph, KIND_LABEL } from '../agents'
import type { ApprovalKind } from '../api'
import { describeTool, type FeedItem } from '../derive'

function time(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function Result({ value }: { value: unknown }) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 1)
  return <pre>{text.length > 900 ? text.slice(0, 900) + ' …' : text}</pre>
}

interface Props { items: FeedItem[]; live: boolean; empty: string; runAt?: string | null }

export function TransmissionFeed({ items, live, empty, runAt }: Props) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (live) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [items.length, live])

  return (
    <section className="panel feed" aria-label="Live transmissions">
      <div className="panel__head">
        <h2>Transmissions</h2>
        <span className={`panel__meta ${live ? 'live-tag' : ''}`}>{live ? '● Live' : runAt ? `Latest run · ${new Date(runAt).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}` : ''}</span>
      </div>
      <div className="feed__scroll" aria-live="polite">
        {!items.length && <p className="feed__empty">{empty}</p>}
        {items.map((it, i) => {
          const e = it.e
          const depth = Math.max(0, e.chain.length - 1)
          switch (it.kind) {
            case 'mission':
              return (
                <div key={i} className="tx tx--mission">
                  <span className="tx__time">{time(e.ts)}</span>
                  <b>Orders received by the Council Master</b>
                  <p>{e.said}</p>
                </div>
              )
            case 'jump': {
              const d = e.delegation!
              const status = d.refused ? 'refused' : d.reused_earlier_report ? 'reused' : 'ok'
              return (
                <div key={i} className={`jump jump--${status} jump--to-${d.to}`} style={{ marginLeft: depth * 22 }}>
                  <div className="jump__line" aria-hidden />
                  <div className="jump__label">
                    <span className={`agent-ink agent-ink--${d.from}`}>{AGENTS[d.from].title}</span>
                    <span className="jump__arrow">⟶</span>
                    <span className={`agent-ink agent-ink--${d.to}`}>{AGENTS[d.to].title}</span>
                    {status === 'refused' && <em> · refused: {d.refused}</em>}
                    {status === 'reused' && <em> · reused earlier report</em>}
                  </div>
                  <p className="jump__task">{e.said}</p>
                </div>
              )
            }
            case 'action':
              return (
                <div key={i} className={`tx tx--action agent--${e.agent}`} style={{ marginLeft: depth * 22 }}>
                  <div className="tx__who">
                    <span className="tx__glyph"><AgentGlyph agent={e.agent} size={18} /></span>
                    <b>{AGENTS[e.agent].title}</b>
                    <span className="tx__channel">{e.chain.map(a => AGENTS[a].short).join(' ▸ ')}</span>
                    <span className="tx__time">{time(e.ts)}</span>
                  </div>
                  {e.said && <p className="tx__said">{e.said}</p>}
                  <div className="chips">
                    {it.tools.map((t, j) => (
                      <span key={j} className={`chip ${t.tool === 'delegate' ? 'chip--delegate' : t.tool === 'submit_approval_request' ? 'chip--seal' : ''}`}>
                        {t.tool === 'delegate' ? '↗' : t.tool === 'submit_approval_request' ? '✦' : '⚙'} {describeTool(t)}
                      </span>
                    ))}
                  </div>
                  {it.results && (
                    <details className="tx__results">
                      <summary>{it.results.length} result{it.results.length > 1 ? 's' : ''} received</summary>
                      {it.results.map((r, j) => (
                        <div key={j} className="tx__result"><code>{r.tool}</code>{r.retry && <em> (retry)</em>}<Result value={r.result} /></div>
                      ))}
                    </details>
                  )}
                </div>
              )
            case 'report': {
              const r = e.report!
              return (
                <div key={i} className={`tx tx--report agent--${e.agent}`} style={{ marginLeft: depth * 22 }}>
                  <div className="tx__who">
                    <span className="tx__glyph"><AgentGlyph agent={e.agent} size={18} /></span>
                    <b>{AGENTS[e.agent].title} reports</b>
                    <span className="tx__time">{time(e.ts)}</span>
                  </div>
                  <p className="tx__said">{r.summary}</p>
                  {r.approvals_requested.length > 0 && (
                    <div className="chips">
                      {r.approvals_requested.map(a => (
                        <span key={a.approval_id} className="chip chip--seal">✦ #{a.approval_id} {KIND_LABEL[a.kind as ApprovalKind] ?? a.kind}{a.amount != null ? ` · $${a.amount.toLocaleString()}` : ''}</span>
                      ))}
                    </div>
                  )}
                </div>
              )
            }
            case 'error':
              return <div key={i} className="tx tx--error">⚠ {AGENTS[e.agent].title}: {e.said}</div>
          }
        })}
        {live && <div className="tx tx--typing"><span /><span /><span /></div>}
        <div ref={end} />
      </div>
    </section>
  )
}
