/**
 * The instruction surface, and the only one.
 *
 * It replaces the chat box rather than hiding it. A persistent message field
 * makes typing look like the job and makes the product look like it is waiting
 * to be told what to do; a bar that does not exist until ⌘K is pressed leaves
 * the resting state of the screen as a company operating.
 *
 * Two kinds of input arrive here and they are answered differently. A question
 * is answered from measured state. An instruction is refused, out loud, with
 * the remedy named — the direction was fixed when the run started, and a
 * command bar that quietly accepted "drop the price" would mean the human was
 * steering while the record said the machine did.
 */
import { useEffect, useRef, useState } from 'react'
import { CornerDownLeft, LoaderCircle } from 'lucide-react'

const SUGGESTIONS = [
  '今いくら入ってる？',
  'なぜ止まっている？',
  'どこまで進んだ？',
  '何を売っている？',
]

export function CommandBar({ onClose, onRan }: { onClose: () => void; onRan: () => void }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [reply, setReply] = useState<{ text: string; refused: boolean } | null>(null)
  const field = useRef<HTMLInputElement>(null)

  useEffect(() => { field.current?.focus() }, [])

  const run = async (asked: string) => {
    const question = asked.trim()
    if (!question || busy) return
    setBusy(true); setReply(null)
    try {
      const response = await fetch('/v1/ask', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!response.ok) throw new Error()
      const body = await response.json()
      setReply({ text: body.text, refused: body.refused })
      onRan()
    } catch {
      setReply({ text: '答えを取得できませんでした。', refused: false })
    }
    setBusy(false)
  }

  return <>
    <button
      aria-label='close'
      onClick={onClose}
      className='fixed inset-0 z-40 cursor-default bg-[#121212]/20'
    />
    <div className='fixed left-1/2 top-[18vh] z-50 w-[min(560px,90vw)] -translate-x-1/2 overflow-hidden rounded-xl border border-[#dcdad5] bg-white shadow-[0_16px_48px_-12px_rgba(0,0,0,0.18)]'>
      <div className='flex items-center gap-3 px-4'>
        <input
          ref={field}
          value={text}
          onChange={event => setText(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter') { event.preventDefault(); void run(text) }
          }}
          placeholder='会社について聞く'
          className='h-12 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-[#c4c1ba]'
        />
        {busy
          ? <LoaderCircle className='size-4 shrink-0 animate-spin text-[#9d9a94]' />
          : <CornerDownLeft className='size-3.5 shrink-0 text-[#c4c1ba]' />}
      </div>

      {reply ? (
        <div className='border-t border-[#eeece7] bg-[#f7f5f1] px-4 py-3'>
          <p className={`text-[13px] leading-6 ${reply.refused ? 'text-[#c23a08]' : 'text-[#121212]'}`}>
            {reply.text}
          </p>
        </div>
      ) : (
        <div className='border-t border-[#eeece7] py-1.5'>
          {SUGGESTIONS.map(item => (
            <button
              key={item}
              onClick={() => { setText(item); void run(item) }}
              className='block w-full px-4 py-1.5 text-left text-[13px] text-[#616161] hover:bg-[#f7f5f1]'
            >{item}</button>
          ))}
        </div>
      )}
    </div>
  </>
}
