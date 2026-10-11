// Turn raw /api/events entries into what the bridge shows.
import type { AgentEvent, AgentName, AgentReport, ToolUse } from './api'
import { AGENT_ORDER, AGENTS } from './agents'

export type AgentStatus = 'standby' | 'summoned' | 'thinking' | 'working' | 'waiting' | 'reported' | 'error' | 'stood_down'

export interface AgentState {
  agent: AgentName
  status: AgentStatus
  line: string            // one-line "what they're doing / saying now"
  tools: string[]         // distinct MCP tools used this run, in order
  toolCalls: number
  report: AgentReport | null
  summonedBy: AgentName | null
}

/** Only the newest team run among these events. */
export function latestRun(events: AgentEvent[]): AgentEvent[] {
  if (!events.length) return []
  const id = events[events.length - 1].team_run_id
  return events.filter(e => e.team_run_id === id)
}

const HIDDEN_TOOLS = new Set(['final_result'])

export function describeTool(t: ToolUse): string {
  const a = t.args ?? {}
  if (t.tool === 'delegate') return `delegate → ${AGENTS[a.to_agent as AgentName]?.title ?? a.to_agent}`
  if (t.tool === 'submit_approval_request') {
    const amt = typeof a.amount === 'number' ? ` $${a.amount}` : typeof a.unit_price === 'number' ? ` $${a.unit_price}×${a.qty}` : ''
    return `submit_approval_request(${a.kind}${amt})`
  }
  const parts = Object.entries(a)
    .filter(([k]) => !['agent', 'requested_by', 'note', 'summary', 'message', 'task'].includes(k))
    .map(([, v]) => (typeof v === 'string' ? v : JSON.stringify(v)))
  return `${t.tool}(${parts.join(', ')})`
}

export function agentStates(run: AgentEvent[], running: boolean): AgentState[] {
  return AGENT_ORDER.map(agent => {
    const mine = run.filter(e => e.agent === agent && e.event !== 'delegation')
    const tools: string[] = []
    let toolCalls = 0
    for (const e of mine) {
      if (e.event !== 'model_response') continue
      for (const t of e.tools) {
        if (HIDDEN_TOOLS.has(t.tool) || t.tool === 'delegate') continue
        toolCalls++
        if (!tools.includes(t.tool)) tools.push(t.tool)
      }
    }
    const start = mine.find(e => e.event === 'run_start')
    const end = [...mine].reverse().find(e => e.event === 'run_end')
    const last = mine[mine.length - 1]
    const base = { agent, tools, toolCalls, report: end?.report ?? null, summonedBy: start?.delegated_by ?? null }

    if (!last) return { ...base, status: running ? 'standby' : run.length ? 'stood_down' : 'standby', line: running ? 'On standby' : run.length ? 'Not called on this mission' : 'Awaiting orders' }
    if (last.event === 'error') return { ...base, status: 'error', line: last.said ?? 'Error' }
    if (last.event === 'run_end') return { ...base, status: 'reported', line: end?.report?.summary ?? 'Reported' }
    if (last.event === 'model_response') {
      const visible = last.tools.filter(t => !HIDDEN_TOOLS.has(t.tool))
      const deleg = visible.filter(t => t.tool === 'delegate')
      if (deleg.length && deleg.length === visible.length)
        return { ...base, status: 'waiting', line: `Waiting on ${deleg.map(d => AGENTS[d.args?.to_agent as AgentName]?.title).join(', ')}` }
      if (visible.length) return { ...base, status: 'working', line: visible.map(describeTool).join(' · ') }
      return { ...base, status: 'thinking', line: 'Writing report…' }
    }
    if (last.event === 'run_start') return { ...base, status: 'summoned', line: 'Reading the orders…' }
    return { ...base, status: 'thinking', line: 'Considering the results…' }
  })
}

export function runUsage(run: AgentEvent[]) {
  let input = 0, output = 0, requests = 0
  for (const e of run) {
    if (e.event !== 'model_response') continue
    requests++
    input += Number(e.usage.input_tokens ?? 0)
    output += Number(e.usage.output_tokens ?? 0)
  }
  return { input, output, requests }
}

export type FeedItem =
  | { kind: 'mission'; e: AgentEvent }
  | { kind: 'jump'; e: AgentEvent }
  | { kind: 'action'; e: AgentEvent; tools: ToolUse[]; results?: ToolUse[] }
  | { kind: 'report'; e: AgentEvent }
  | { kind: 'error'; e: AgentEvent }

/** Collapse the raw step log into readable transmissions; tool results attach to the action that asked for them. */
export function feedItems(run: AgentEvent[]): FeedItem[] {
  const items: FeedItem[] = []
  const pendingByRun = new Map<string, Extract<FeedItem, { kind: 'action' }>>()
  for (const e of run) {
    if (e.event === 'run_start' && e.agent === 'boss') items.push({ kind: 'mission', e })
    else if (e.event === 'delegation') items.push({ kind: 'jump', e })
    else if (e.event === 'model_response') {
      const tools = e.tools.filter(t => !HIDDEN_TOOLS.has(t.tool))
      if (!tools.length) continue // the final answer shows up as the report card
      const item = { kind: 'action' as const, e, tools }
      items.push(item)
      pendingByRun.set(e.run_id, item)
    } else if (e.event === 'tool_results') {
      const owner = pendingByRun.get(e.run_id)
      const results = e.tools.filter(t => !HIDDEN_TOOLS.has(t.tool))
      if (owner && results.length) owner.results = results
    } else if (e.event === 'run_end') items.push({ kind: 'report', e })
    else if (e.event === 'error') items.push({ kind: 'error', e })
  }
  return items
}
