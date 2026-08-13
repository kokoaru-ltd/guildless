/**
 * Adapted from cloudflare/cloudflare-os
 * packages/workshop-frontend/src/components/AppShell/HomeTaskSuggestions.tsx
 * commit c04843f97cd07a8c869312058fc59a00b5d5b5cb
 * Licensed under Apache-2.0. See THIRD_PARTY_NOTICES.md.
 *
 * The retained interaction rule is important: choosing a suggestion fills the
 * composer but never sends it automatically. The founder stays in control.
 */
import type { LucideIcon } from 'lucide-react'
import { ArrowUpRight, BriefcaseBusiness, MessagesSquare, Search, UsersRound } from 'lucide-react'

export type GuildlessPromptMode = 'consult' | 'organize' | 'council' | 'delegate'

type Suggestion = {
  id: GuildlessPromptMode
  label: string
  description: string
  prompt: string
  icon: LucideIcon
  tone: string
}

const SUGGESTIONS: Suggestion[] = [
  {
    id: 'consult',
    label: '壁打ちする',
    description: '考えを言葉にして、次の一手を整理',
    prompt: 'いま考えていることを整理したい。前提を確認しながら、次に決めるべきことを一緒に絞って。',
    icon: MessagesSquare,
    tone: 'bg-[#f6eee7] text-[#a94712]',
  },
  {
    id: 'organize',
    label: '状況を整理する',
    description: '情報を要点・不明点・リスクに分ける',
    prompt: 'この状況を、確認できている事実・不明点・リスク・次に集める情報に分けて整理して。',
    icon: Search,
    tone: 'bg-[#e8f1ee] text-[#276453]',
  },
  {
    id: 'council',
    label: '経営会議を開く',
    description: '複数の視点で選択肢を比較',
    prompt: 'この判断について、賛成・反対・財務・実行の観点から比較し、決めるための材料を出して。',
    icon: UsersRound,
    tone: 'bg-[#ececf5] text-[#4d4b87]',
  },
  {
    id: 'delegate',
    label: '仕事を任せる',
    description: '目的から調査・実装・検証まで依頼',
    prompt: 'この目的を達成するために、既存OSSを調べ、最短の実装案を選び、検証可能な成果物まで作って。',
    icon: BriefcaseBusiness,
    tone: 'bg-[#f3ead7] text-[#8a6119]',
  },
]

export function HomeTaskSuggestions({
  onPick,
}: {
  onPick: (suggestion: Pick<Suggestion, 'id' | 'prompt' | 'label'>) => void
}) {
  return (
    <section aria-label='Guildlessでできること'>
      <div className='mb-3 flex items-center gap-3'>
        <h2 className='text-[11px] font-semibold uppercase tracking-[.12em] text-[#77746e]'>すぐに始める</h2>
        <div className='h-px flex-1 bg-[#dedcd7]' />
      </div>
      <div className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
        {SUGGESTIONS.map(item => (
          <button
            key={item.id}
            type='button'
            onClick={() => onPick(item)}
            className='group min-h-36 rounded-2xl border border-[#dedcd7] bg-white p-4 text-left shadow-[0_1px_0_rgba(20,17,15,.03)] transition duration-200 hover:-translate-y-0.5 hover:border-[#c9c6bf] hover:shadow-[0_12px_30px_rgba(35,29,24,.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4801]/50'
          >
            <span className={`mb-5 grid size-10 place-items-center rounded-xl ${item.tone}`}>
              <item.icon className='size-[19px]' />
            </span>
            <span className='flex items-center justify-between gap-3'>
              <span className='text-sm font-semibold text-[#171513]'>{item.label}</span>
              <ArrowUpRight className='size-4 text-[#aaa69e] transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[#ff4801]' />
            </span>
            <span className='mt-1.5 block text-xs leading-5 text-[#77746e]'>{item.description}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
