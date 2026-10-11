import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, usd, type AgentEvent, type Approval, type Cash, type RunResult, type Ticket } from './api'
import { agentStates, feedItems, latestRun, runUsage } from './derive'
import { TopBar } from './components/TopBar'
import { TicketBoard } from './components/TicketBoard'
import { MissionBriefing } from './components/MissionBriefing'
import { CouncilRoster } from './components/CouncilRoster'
import { TransmissionFeed } from './components/TransmissionFeed'
import { Debrief } from './components/Debrief'
import { ApprovalQueue } from './components/ApprovalQueue'
import { CashPanel } from './components/CashPanel'
import { Crawl } from './components/Crawl'
import type { Theme } from './components/SaberToggle'

interface Toast { id: number; tone: 'ok' | 'warn' | 'bad'; text: string }
interface Running { ticketId: number; since: string | null; startedAt: number }

const initialTheme = (): Theme =>
  (localStorage.getItem('cc-theme') as Theme | null) ??
  (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'sith' : 'jedi')

export default function App() {
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const [officer, setOfficer] = useState(() => localStorage.getItem('cc-officer') ?? '')
  const [officerNeeded, setOfficerNeeded] = useState(false)
  const [crawl, setCrawl] = useState(() => !sessionStorage.getItem('cc-crawled'))

  const [online, setOnline] = useState<boolean | null>(null)
  const [model, setModel] = useState<string | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [running, setRunning] = useState<Running | null>(null)
  const [serverRunning, setServerRunning] = useState<number | null>(null)
  const [results, setResults] = useState<Record<number, RunResult>>({})
  const [justResolved, setJustResolved] = useState<Set<number>>(new Set())
  const [busyApproval, setBusyApproval] = useState<number | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const prevStates = useRef<Record<number, string>>({})

  // ---------------------------------------------------------------- theme & prefs
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('cc-theme', theme)
  }, [theme])
  useEffect(() => { localStorage.setItem('cc-officer', officer) }, [officer])

  const toast = useCallback((tone: Toast['tone'], text: string) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, tone, text }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6500)
  }, [])

  // ---------------------------------------------------------------- data
  const refresh = useCallback(async () => {
    try {
      const [t, c, a, h] = await Promise.all([api.tickets(), api.cash(), api.approvals('all'), api.health()])
      setOnline(true)
      setModel(h.model)
      setServerRunning(t.running_ticket)
      setCash(c)
      setApprovals(a.requests)
      // spot tickets that just flipped to resolved so their stamp can animate in
      const flipped = t.tickets.filter(x => x.state === 'resolved' && prevStates.current[x.id] === 'open').map(x => x.id)
      if (flipped.length) {
        setJustResolved(s => new Set([...s, ...flipped]))
        setTimeout(() => setJustResolved(s => new Set([...s].filter(id => !flipped.includes(id)))), 2500)
      }
      prevStates.current = Object.fromEntries(t.tickets.map(x => [x.id, x.state]))
      setTickets(t.tickets)
      setSelected(s => s ?? t.tickets.find(x => x.state === 'open')?.id ?? t.tickets[0]?.id ?? null)
    } catch {
      setOnline(false)
    }
  }, [])

  const loadRun = useCallback(async (ticketId: number, since?: string | null) => {
    try {
      const r = await api.events({ ticket_id: ticketId, since: since ?? undefined, limit: 500 })
      setEvents(latestRun(r.events))
    } catch { /* uplink toast comes from refresh */ }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [refresh])

  // switching tickets shows that ticket's latest run
  useEffect(() => {
    if (selected == null) return
    setEvents([])
    if (running?.ticketId === selected) loadRun(selected, running.since)
    else loadRun(selected)
  }, [selected]) // only on ticket switch; live polling is handled below

  // live polling while the council is in session on the ticket we're looking at
  const liveTicket = running?.ticketId ?? serverRunning
  const liveHere = liveTicket != null && liveTicket === selected
  useEffect(() => {
    if (!liveHere || selected == null) return
    const since = running?.ticketId === selected ? running.since : null
    const id = setInterval(() => loadRun(selected, since), 1200)
    return () => clearInterval(id)
  }, [liveHere, selected, running, loadRun])

  // ---------------------------------------------------------------- actions
  const engage = useCallback(async () => {
    if (selected == null) return
    const ticketId = selected
    let since: string | null = null
    try { since = (await api.events({ limit: 1 })).latest_ts } catch { /* first run ever */ }
    setRunning({ ticketId, since, startedAt: Date.now() })
    setEvents([])
    toast('ok', `Council dispatched to ticket #${ticketId}.`)
    try {
      const r = await api.runTicket(ticketId)
      setResults(x => ({ ...x, [ticketId]: r }))
      if (r.ok) toast('ok', `Ticket #${ticketId} resolved. ${r.report?.approvals_requested.length ?? 0} request(s) await your seal.`)
      else toast('bad', `Run on #${ticketId} failed: ${r.error}`)
    } catch (e) {
      toast('bad', `Couldn't run #${ticketId}: ${(e as Error).message}`)
    } finally {
      setRunning(null)
      await loadRun(ticketId, since)
      await refresh()
    }
  }, [selected, toast, loadRun, refresh])

  const decide = useCallback(async (a: Approval, decision: 'approve' | 'reject', note = '') => {
    if (!officer.trim()) {
      setOfficerNeeded(true)
      document.getElementById('officer-input')?.focus()
      toast('warn', 'Sign in as desk officer first. Every decision is recorded with a human name.')
      return
    }
    setOfficerNeeded(false)
    setBusyApproval(a.id)
    try {
      const r = await api.decide(a.id, decision, officer.trim(), note.trim())
      if (r.amount_paid != null) toast('ok', `Paid ${usd(r.amount_paid)}. Checking ${usd(r.cash_before)} → ${usd(r.cash_after)}.`)
      else toast('ok', `Request #${a.id} ${r.decision}.`)
      r.warnings.forEach(w => toast('warn', w))
    } catch (e) {
      toast('bad', (e as Error).message)
    } finally {
      setBusyApproval(null)
      refresh()
    }
  }, [officer, toast, refresh])

  const reset = useCallback(async () => {
    if (!window.confirm('Reset the shop database to the original data? Approvals, payments and ticket statuses are wiped (the audit trail is kept).')) return
    try {
      const r = await api.reset()
      setResults({})
      setEvents([])
      toast('ok', `Database reset. Checking back to ${usd(r.checking_balance)}.`)
      await refresh()
    } catch (e) {
      toast('bad', `Reset failed: ${(e as Error).message}`)
    }
  }, [refresh, toast])

  // ---------------------------------------------------------------- derived
  const ticket = tickets.find(t => t.id === selected) ?? null
  const isLive = liveHere
  const states = useMemo(() => agentStates(events, isLive), [events, isLive])
  const items = useMemo(() => feedItems(events), [events])
  const usage = useMemo(() => runUsage(events), [events])
  const pending = approvals.filter(a => a.status === 'pending').length

  return (
    <div className="app">
      <div className="sky" aria-hidden />
      {crawl && <Crawl onDone={() => { sessionStorage.setItem('cc-crawled', '1'); setCrawl(false) }} />}

      <TopBar
        theme={theme}
        onToggleTheme={() => setTheme(t => (t === 'jedi' ? 'sith' : 'jedi'))}
        officer={officer}
        onOfficer={v => { setOfficer(v); if (v.trim()) setOfficerNeeded(false) }}
        officerNeeded={officerNeeded}
        pending={pending}
        online={online}
        model={model}
        onReset={reset}
        onReplayCrawl={() => setCrawl(true)}
      />

      {online === false && (
        <div className="offline">
          Can't reach the backend at <code>http://localhost:8000</code>. Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="bridge">
        <aside className="col col--left">
          <TicketBoard tickets={tickets} selected={selected} running={liveTicket} justResolved={justResolved} onSelect={setSelected} />
          <CashPanel cash={cash} approvals={approvals} />
        </aside>

        <section className="col col--center">
          {ticket ? (
            <>
              <MissionBriefing
                ticket={ticket}
                runningHere={isLive}
                busyElsewhere={liveTicket != null && liveTicket !== ticket.id ? liveTicket : null}
                startedAt={running?.ticketId === ticket.id ? running.startedAt : isLive && events[0] ? Date.parse(events[0].ts) : null}
                usage={usage}
                lastResult={results[ticket.id] ?? null}
                onEngage={engage}
              />
              <CouncilRoster states={states} />
              <TransmissionFeed
                items={items}
                live={isLive}
                runAt={events[0]?.ts ?? null}
                empty={isLive ? 'Opening the channel…' : 'No transmissions yet. Dispatch the Council to watch the agents work this ticket.'}
              />
            </>
          ) : (
            <section className="panel"><p className="muted">Loading the mission board…</p></section>
          )}
        </section>

        <aside className="col col--right">
          <ApprovalQueue approvals={approvals} ticketId={selected} balance={cash?.balance ?? null} floor={cash?.cash_floor ?? 500} busyId={busyApproval} onDecide={decide} />
          <Debrief states={states} hasRun={events.length > 0} />
        </aside>
      </main>

      <div className="toasts" aria-live="assertive">
        {toasts.map(t => <div key={t.id} className={`toast toast--${t.tone}`}>{t.text}</div>)}
      </div>
    </div>
  )
}
