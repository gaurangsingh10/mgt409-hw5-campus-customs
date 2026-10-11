// Each agent gets its own identity on the bridge: a council title, a color and an emblem.
import type { AgentName, ApprovalKind } from './api'

export interface AgentMeta {
  name: AgentName
  title: string     // in-universe council title
  role: string      // plain-English job
  short: string     // 3-letter callsign used on channel labels
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: { name: 'boss', title: 'Council Master', role: 'Boss · triage & routing', short: 'CMD' },
  inventory: { name: 'inventory', title: 'Quartermaster', role: 'Inventory · stock & vendors', short: 'QM' },
  accounting: { name: 'accounting', title: 'Treasury Droid', role: 'Accounting · cash & pricing', short: 'TRS' },
  facilities: { name: 'facilities', title: 'Hangar Chief', role: 'Facilities · lease & rent', short: 'HGR' },
  customer_service: { name: 'customer_service', title: 'Protocol Droid', role: 'Customer Service · replies', short: 'PRT' },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const KIND_LABEL: Record<ApprovalKind, string> = {
  pay_invoice: 'Pay vendor invoice',
  pay_rent: 'Pay rent',
  restock_order: 'Restock purchase',
  price_override: 'Bulk discount',
  customer_reply: 'Customer reply',
}

/** Original emblems, simple geometry, one per agent. */
export function AgentGlyph({ agent, size = 28 }: { agent: AgentName; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 32 32', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }
  switch (agent) {
    case 'boss': // council seal: ring with four rays
      return (
        <svg {...common} aria-hidden>
          <circle cx="16" cy="16" r="7" />
          <circle cx="16" cy="16" r="2.5" fill="currentColor" />
          <path d="M16 2v6M16 24v6M2 16h6M24 16h6" strokeLinecap="round" />
        </svg>
      )
    case 'inventory': // stacked crates
      return (
        <svg {...common} aria-hidden>
          <rect x="4" y="16" width="11" height="11" rx="1.5" />
          <rect x="17" y="16" width="11" height="11" rx="1.5" />
          <rect x="10.5" y="4" width="11" height="11" rx="1.5" />
          <path d="M4 21.5h11M17 21.5h11M10.5 9.5h11" />
        </svg>
      )
    case 'accounting': // hex credit chip
      return (
        <svg {...common} aria-hidden>
          <path d="M16 3l11 6.5v13L16 29 5 22.5v-13z" />
          <path d="M19.5 12.5c-.8-1-2-1.5-3.5-1.5-2 0-3.5 1-3.5 2.5 0 3.5 7 1.8 7 5 0 1.6-1.6 2.5-3.5 2.5-1.6 0-2.9-.6-3.7-1.6M16 9v2M16 21v2" strokeLinecap="round" />
        </svg>
      )
    case 'facilities': // hangar arch
      return (
        <svg {...common} aria-hidden>
          <path d="M3 28V15C3 8.4 8.8 4 16 4s13 4.4 13 11v13" />
          <path d="M9 28V18h14v10M9 22.5h14" />
        </svg>
      )
    case 'customer_service': // protocol transmission diamond
      return (
        <svg {...common} aria-hidden>
          <path d="M16 3l13 13-13 13L3 16z" />
          <path d="M11 14.5h10M11 18.5h6" strokeLinecap="round" />
        </svg>
      )
  }
}
