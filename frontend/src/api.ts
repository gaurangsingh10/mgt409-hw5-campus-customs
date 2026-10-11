// Typed client for the Campus Customs FastAPI backend (backend/main.py).
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type ApprovalKind = 'pay_invoice' | 'pay_rent' | 'price_override' | 'restock_order' | 'customer_reply'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  state: 'open' | 'resolved'
  notes: string | null
  created_at: string
  pending_approvals: number
}

export interface ApprovalRef { approval_id: number; kind: ApprovalKind; amount: number | null; summary: string }

export interface AgentReport {
  agent: AgentName
  ticket_ids: number[]
  summary: string
  facts: string[]
  actions_taken: string[]
  approvals_requested: ApprovalRef[]
  needs_human: boolean
  open_questions: string[]
  next_steps: string[]
}

export interface ToolUse { tool: string; args?: Record<string, unknown>; result?: unknown; retry?: boolean }

export interface AgentEvent {
  ts: string
  ticket_id: number | null
  team_run_id: string
  run_id: string
  agent: AgentName
  delegated_by: AgentName | null
  chain: AgentName[]
  step: number
  event: 'run_start' | 'user_prompt' | 'model_response' | 'tool_results' | 'delegation' | 'run_end' | 'error'
  said: string | null
  tools: ToolUse[]
  usage: Record<string, unknown>
  delegation?: { from: AgentName; to: AgentName; refused: string | null; reused_earlier_report?: boolean }
  report?: AgentReport
}

export interface EventsResponse { count: number; latest_ts: string | null; running_ticket: number | null; events: AgentEvent[] }

export interface Approval {
  id: number
  ticket_id: number
  kind: ApprovalKind
  ref_id: number | null
  amount: number | null
  unit_price: number | null
  qty: number | null
  vendor_id: number | null
  message: string | null
  summary: string
  requested_by: AgentName
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  open_invoices_total: number
  rent_due_total: number
  cash_after_all_obligations: number
  cash_floor: number
}

export interface RunResult {
  team_run_id: string
  ticket_id: number
  ok: boolean
  report: AgentReport | null
  error: string | null
  usage: Record<string, number>
}

export interface DecisionResult {
  ok: boolean
  approval_id: number
  kind: ApprovalKind
  decision: 'approved' | 'rejected'
  cash_before: number
  cash_after: number
  amount_paid?: number
  warnings: string[]
  ticket_id: number
  ticket_status: string
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* not JSON */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => call<{ ok: boolean; model: string; running_ticket: number | null }>('/api/health'),
  tickets: () => call<{ tickets: Ticket[]; running_ticket: number | null }>('/api/tickets'),
  runTicket: (id: number) => call<RunResult>(`/api/tickets/${id}/run`, { method: 'POST' }),
  events: (q: { ticket_id?: number; since?: string | null; limit?: number; team_run_id?: string }) => {
    const p = new URLSearchParams()
    if (q.ticket_id != null) p.set('ticket_id', String(q.ticket_id))
    if (q.since) p.set('since', q.since)
    if (q.team_run_id) p.set('team_run_id', q.team_run_id)
    p.set('limit', String(q.limit ?? 500))
    return call<EventsResponse>(`/api/events?${p}`)
  },
  approvals: (status: 'pending' | 'approved' | 'rejected' | 'all' = 'all') =>
    call<{ count: number; requests: Approval[] }>(`/api/approvals?status=${status}`),
  decide: (id: number, decision: 'approve' | 'reject', approver: string, note = '') =>
    call<DecisionResult>(`/api/approvals/${id}/${decision}`, { method: 'POST', body: JSON.stringify({ approver, note }) }),
  cash: () => call<Cash>('/api/cash'),
  reset: () => call<{ ok: boolean; checking_balance: number }>('/api/reset', { method: 'POST' }),
}

export const MONEY_KINDS: ApprovalKind[] = ['pay_invoice', 'pay_rent', 'restock_order']

export const usd = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
