import { useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, LoaderCircle, Megaphone, ShieldCheck, Sparkles, Target } from 'lucide-react'
import { Button } from '@/components/ui/button'

type SourcePack = {
  id: string
  name: string
  repository: string
  role: string
  installed: boolean
  source_url: string
}

type PipelineStage = { order: number; title: string }
type MarketingRole = { id: string; name: string; lane: string; description: string }
type SalesOverview = {
  status: 'ready' | 'setup_required'
  mode: 'shadow'
  external_sending_enabled: boolean
  packs: SourcePack[]
  pipeline?: PipelineStage[]
  marketing_team?: MarketingRole[]
  heartbeat_checks?: string[]
}

type LeadScore = {
  company: string
  bant_score: number
  lead_grade: string
  confidence_level: string
  recommended_action: string
  external_actions_performed: boolean
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`)
  return body as T
}

const demoLead = {
  company: 'サンプル製造株式会社',
  budget_signals: { employee_count: 120, pricing_visible: true, tech_spend_indicators: ['CTI', 'CRM'] },
  authority_signals: { decision_makers_found: 2, c_suite_identified: true, org_chart_mapped: false },
  need_signals: { pain_points_detected: 3, job_posts_relevant: true, reviews_mention_pain: true, competitor_complaints: 1 },
  timeline_signals: { hiring_for_role: true, recent_funding: false, contract_renewal: true, urgency_mentions: 1 },
}

export function SalesMarketingView() {
  const [overview, setOverview] = useState<SalesOverview | null>(null)
  const [score, setScore] = useState<LeadScore | null>(null)
  const [loading, setLoading] = useState(true)
  const [scoring, setScoring] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    jsonRequest<SalesOverview>('/v1/sales/overview')
      .then(setOverview)
      .catch(reason => setError(reason instanceof Error ? reason.message : '営業OSSを読み込めませんでした'))
      .finally(() => setLoading(false))
  }, [])

  const runDemo = async () => {
    setScoring(true)
    setError('')
    try {
      setScore(await jsonRequest<LeadScore>('/v1/sales/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(demoLead),
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '採点できませんでした')
    } finally {
      setScoring(false)
    }
  }

  if (loading) return <div className='grid h-[calc(100svh-8rem)] place-items-center'><LoaderCircle className='size-5 animate-spin text-[#ff4801]' /></div>

  return <div className='grid h-[calc(100svh-8rem)] min-h-[620px] gap-4 overflow-hidden xl:grid-cols-[1.2fr_.8fr]'>
    <section className='flex min-h-0 flex-col rounded-[22px] border border-[#dedbd4] bg-white p-5 lg:p-6'>
      <header className='flex items-start justify-between gap-4'>
        <div><p className='text-[11px] font-semibold tracking-[.12em] text-[#817d76]'>GROWTH</p><h1 className='mt-1 text-2xl font-semibold tracking-[-.035em]'>営業・マーケ</h1><p className='mt-1 text-sm text-[#77736d]'>既存OSSを組み合わせ、送信直前で止めます。</p></div>
        <span className='inline-flex items-center gap-2 rounded-full bg-[#eaf3ef] px-3 py-1.5 text-xs font-medium text-[#276453]'><ShieldCheck className='size-3.5' />Shadow Mode</span>
      </header>

      {error && <p className='mt-4 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700'>{error}</p>}

      <div className='mt-5 grid grid-cols-3 gap-2'>
        <Summary value={overview?.packs.filter(pack => pack.installed).length || 0} label='接続OSS' />
        <Summary value={overview?.pipeline?.length || 0} label='営業段階' />
        <Summary value={overview?.heartbeat_checks?.length || 0} label='定期確認' />
      </div>

      <div className='mt-5 min-h-0 flex-1 rounded-2xl bg-[#f5f3ef] p-4'>
        <div className='flex items-center gap-2'><Target className='size-4 text-[#ff4801]' /><h2 className='text-sm font-semibold'>営業パイプライン</h2><span className='ml-auto text-[10px] text-[#8b877f]'>b2b-sdr-agent-template</span></div>
        <div className='mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-5'>
          {(overview?.pipeline || []).map(stage => <div key={stage.order} className='flex min-w-0 items-center gap-2 rounded-lg bg-white px-2.5 py-2'>
            <span className='grid size-5 shrink-0 place-items-center rounded-full bg-[#171513] text-[9px] font-semibold text-white'>{stage.order}</span>
            <p className='truncate text-[11px] font-medium text-[#45413c]' title={stage.title}>{stage.title}</p>
          </div>)}
        </div>
      </div>

      <div className='mt-4 grid grid-cols-4 gap-2'>
        {(overview?.marketing_team || []).map(role => <div key={role.id} className='rounded-xl border border-[#e4e1da] px-3 py-3'>
          <p className='text-[10px] font-semibold text-[#ff4801]'>{role.lane}</p><p className='mt-1 text-sm font-semibold'>{role.name}</p><p className='mt-1 line-clamp-2 text-[10px] leading-4 text-[#817d76]'>{role.description}</p>
        </div>)}
      </div>
    </section>

    <aside className='flex min-h-0 flex-col rounded-[22px] border border-[#dedbd4] bg-[#171513] p-5 text-white lg:p-6'>
      <div className='flex items-center gap-3'><span className='grid size-10 place-items-center rounded-xl bg-white/10'><Sparkles className='size-[18px] text-[#ff9d75]' /></span><div><p className='text-sm font-semibold'>企業の優先度を採点</p><p className='text-xs text-white/50'>AI Sales Teamの実コードを使用</p></div></div>

      <div className='mt-5 rounded-2xl border border-white/10 bg-white/[.06] p-4'>
        <p className='text-xs text-white/50'>対象</p><p className='mt-1 text-lg font-semibold'>{demoLead.company}</p>
        <div className='mt-4 grid grid-cols-2 gap-2 text-xs text-white/65'><p>従業員 120名</p><p>決裁者 2名</p><p>課題シグナル 3件</p><p>契約更新あり</p></div>
      </div>

      {score ? <div className='mt-4 flex min-h-0 flex-1 flex-col rounded-2xl bg-white p-5 text-[#171513]'>
        <div className='flex items-start justify-between'><div><p className='text-xs text-[#77736d]'>BANT SCORE</p><p className='mt-1 text-5xl font-semibold tracking-[-.07em]'>{score.bant_score}</p></div><span className='grid size-12 place-items-center rounded-full bg-[#eaf3ef] text-lg font-semibold text-[#276453]'>{score.lead_grade}</span></div>
        <p className='mt-5 text-xs font-semibold text-[#77736d]'>次の行動</p><p className='mt-2 text-sm leading-6'>{score.recommended_action}</p>
        <div className='mt-auto flex items-center gap-2 pt-4 text-xs text-[#276453]'><CheckCircle2 className='size-4' />外部送信なし・採点のみ</div>
      </div> : <div className='mt-4 flex flex-1 flex-col justify-center text-center'><Megaphone className='mx-auto size-8 text-white/25' /><p className='mt-3 text-sm text-white/65'>公開サンプル情報だけで<br />見込み度と次の行動を出します。</p></div>}

      <Button onClick={runDemo} disabled={scoring || overview?.status !== 'ready'} className='mt-4 h-12 rounded-xl bg-[#ff6b32] text-white hover:bg-[#ff4801]'>
        {scoring ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}{scoring ? '採点中' : score ? 'もう一度採点' : 'サンプルを採点'}
      </Button>
    </aside>
  </div>
}

function Summary({ value, label }: { value: number; label: string }) {
  return <div className='rounded-xl border border-[#e4e1da] px-4 py-3'><p className='text-2xl font-semibold tracking-[-.05em]'>{value}</p><p className='mt-0.5 text-[11px] text-[#817d76]'>{label}</p></div>
}
