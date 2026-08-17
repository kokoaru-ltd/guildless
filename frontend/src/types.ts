export type Bet = {
  id: string
  name: string
  offer: string
  audience: string
  channel: string
  price_yen: number
  status: 'PAYING' | 'SCALE' | 'TEST' | 'WATCH' | 'KILLED'
  why: string
  contacted: number
  replied: number
  meetings: number
  quoted: number
  cash_yen: number
  spent_yen: number
  net_yen: number
  pipeline_yen: number
  reply_rate: number
  days_to_first_cash: number | null
  killed_because: string
}

export type Funnel = {
  contacted: number
  replied: number
  meetings: number
  quoted: number
  paid: number
}

export type ActivityItem = {
  at: string
  step: string
  detail: string
  external: boolean
}

export type Company = {
  company: string
  operating: boolean
  money: {
    cash_yen: number
    received_yen: number
    payments: number
    expected_yen: number
    opportunities: number
    capital_yen: number
    simulated_yen: number
    simulated_sales: number
    world: string
  }
  outcome: { statement: string; target_yen: number; progress: number }
  decision: string
  bets: { bets: Bet[]; funnel: Funnel; focus_id: string; decision: string; pipeline_yen: number }
  needs_you: { task: string; title: string; detail: string }[]
  activity: ActivityItem[]
}
