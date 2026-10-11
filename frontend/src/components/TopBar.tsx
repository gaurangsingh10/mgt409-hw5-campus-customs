import { SaberToggle, type Theme } from './SaberToggle'

interface Props {
  theme: Theme
  onToggleTheme: () => void
  officer: string
  onOfficer: (v: string) => void
  officerNeeded: boolean
  pending: number
  online: boolean | null
  model: string | null
  onReset: () => void
  onReplayCrawl: () => void
}

export function TopBar(p: Props) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand__mark" aria-hidden>
          <svg viewBox="0 0 40 40" width="38" height="38">
            <circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M20 6l4 10h10l-8 6 3 11-9-7-9 7 3-11-8-6h10z" fill="currentColor" opacity=".85" />
          </svg>
        </div>
        <div>
          <h1>Campus Customs <span>Command Bridge</span></h1>
          <p className="brand__sub">Chapel Street outpost · shop date <b>2026-08-31</b></p>
        </div>
      </div>

      <div className="topbar__right">
        <div className={`uplink uplink--${p.online === null ? 'unknown' : p.online ? 'on' : 'off'}`} title={p.online ? `Backend online · model ${p.model}` : 'Backend offline at http://localhost:8000'}>
          <span className="uplink__dot" />
          {p.online === null ? 'Connecting…' : p.online ? <>Uplink · <code>{p.model}</code></> : 'Uplink lost'}
        </div>
        <div className={`seal-count ${p.pending ? 'seal-count--hot' : ''}`} title="Approvals waiting for a human">
          <b>{p.pending}</b> awaiting your seal
        </div>
        <label className={`officer ${p.officerNeeded ? 'officer--needed' : ''}`}>
          <span>Desk officer</span>
          <input
            id="officer-input"
            value={p.officer}
            onChange={e => p.onOfficer(e.target.value)}
            placeholder="Your name"
            autoComplete="name"
          />
        </label>
        <button className="ghost-btn" onClick={p.onReplayCrawl} title="Replay the opening crawl">▶ Crawl</button>
        <button className="ghost-btn ghost-btn--warn" onClick={p.onReset} title="Restore the shop database to the original data">⟲ Reset</button>
        <SaberToggle theme={p.theme} onToggle={p.onToggleTheme} />
      </div>
    </header>
  )
}
