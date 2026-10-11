import { AGENTS, AgentGlyph } from '../agents'
import type { AgentState } from '../derive'

const STATUS_TEXT: Record<AgentState['status'], string> = {
  standby: 'Standby',
  summoned: 'Summoned',
  thinking: 'Thinking',
  working: 'Using tools',
  waiting: 'Waiting',
  reported: 'Reported',
  error: 'Fault',
  stood_down: 'Not called',
}

/** The five seats at the council table, lit up by what each agent is doing right now. */
export function CouncilRoster({ states }: { states: AgentState[] }) {
  return (
    <section className="roster" aria-label="Agent council">
      {states.map(s => {
        const m = AGENTS[s.agent]
        return (
          <article key={s.agent} className={`seat seat--${s.agent} seat--${s.status}`}>
            <header className="seat__head">
              <div className="seat__glyph"><AgentGlyph agent={s.agent} size={20} /></div>
              <div className="seat__names">
                <div className="seat__title">{m.title}</div>
                <div className="seat__role">{m.role}</div>
              </div>
            </header>
            <div className="seat__status"><span className="seat__light" />{STATUS_TEXT[s.status]}</div>
            {s.toolCalls > 0 && <div className="seat__count">{s.toolCalls} tool call{s.toolCalls > 1 ? 's' : ''}</div>}
            <div className="seat__line" title={s.line}>{s.line}</div>
          </article>
        )
      })}
    </section>
  )
}
