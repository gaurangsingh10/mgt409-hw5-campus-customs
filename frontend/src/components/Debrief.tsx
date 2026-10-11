import { AGENTS, AgentGlyph } from '../agents'
import type { AgentState } from '../derive'

/** After-action summary: one card per agent that took part in the latest run on this ticket. */
export function Debrief({ states, hasRun }: { states: AgentState[]; hasRun: boolean }) {
  const involved = states.filter(s => s.status !== 'standby' && s.status !== 'stood_down')
  const skipped = states.filter(s => s.status === 'stood_down')
  return (
    <section className="panel debrief" aria-label="Council debrief">
      <div className="panel__head">
        <h2>Council Debrief</h2>
        <span className="panel__meta">{involved.length ? `${involved.length} agents took part` : ''}</span>
      </div>
      {!hasRun && <p className="muted">No run on this ticket yet. Dispatch the Council and each agent's summary lands here.</p>}
      <div className="debrief__list">
        {involved.map(s => {
          const r = s.report
          return (
            <article key={s.agent} className={`dcard agent--${s.agent}`}>
              <header>
                <span className="dcard__glyph"><AgentGlyph agent={s.agent} size={20} /></span>
                <div>
                  <b>{AGENTS[s.agent].title}</b>
                  <small>{s.summonedBy ? `called by ${AGENTS[s.summonedBy].title}` : 'leads the mission'}</small>
                </div>
              </header>
              <p>{r ? r.summary : s.line}</p>
              {r && r.actions_taken.length > 0 && (
                <ul className="dcard__actions">{r.actions_taken.slice(0, 4).map((a, i) => <li key={i}>{a}</li>)}</ul>
              )}
              {s.tools.length > 0 && (
                <div className="dcard__tools">{s.tools.map(t => <code key={t}>{t}</code>)}</div>
              )}
            </article>
          )
        })}
      </div>
      {hasRun && skipped.length > 0 && (
        <p className="debrief__skipped">Not called: {skipped.map(s => AGENTS[s.agent].title).join(', ')}</p>
      )}
    </section>
  )
}
