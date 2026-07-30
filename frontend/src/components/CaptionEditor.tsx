import { useEffect, useState } from 'react'

import { formatTimecode, type Word } from '../api'

/**
 * Word-level caption editing.
 *
 * The job here is fixing what Whisper misheard — names, jargon, acronyms. Only
 * the text is editable; timings stay locked to the measured audio, because a
 * hand-typed timestamp is how captions drift out of sync.
 */
export function CaptionEditor({
  words,
  onChange,
  onSave,
  saving,
  dirty,
}: {
  words: Word[]
  onChange: (words: Word[]) => void
  onSave: () => void
  saving: boolean
  dirty: boolean
}) {
  const [editing, setEditing] = useState<number | null>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => setEditing(null), [words.length])

  const commit = (index: number) => {
    const text = draft.trim()
    if (text && text !== words[index].text) {
      const next = words.map((word, i) => (i === index ? { ...word, text } : word))
      onChange(next)
    }
    setEditing(null)
  }

  if (words.length === 0) {
    return (
      <p className="text-sm text-ink-500">
        No transcript for this clip yet.
      </p>
    )
  }

  return (
    <div>
      <div className="flex items-baseline justify-between border-b border-ink-800 pb-2">
        <span className="eyebrow">Transcript</span>
        <span className="numeric text-xs text-ink-600">{words.length} words</span>
      </div>

      {/* Words flow as text, not as a list of rows — reading it back is the
          main way you notice a mistranscription. */}
      <div className="mt-4 max-h-[38vh] overflow-y-auto pr-1 text-[0.9375rem] leading-[1.9]">
        {words.map((word, index) =>
          editing === index ? (
            <input
              key={index}
              autoFocus
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={() => commit(index)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commit(index)
                if (e.key === 'Escape') setEditing(null)
                if (e.key === 'Tab') {
                  e.preventDefault()
                  commit(index)
                  const next = index + (e.shiftKey ? -1 : 1)
                  if (next >= 0 && next < words.length) {
                    setDraft(words[next].text)
                    setEditing(next)
                  }
                }
              }}
              className="mr-1 w-[8ch] border-b border-sodium-500 bg-transparent px-0.5 text-ink-100 outline-none"
              style={{ width: `${Math.max(4, draft.length + 1)}ch` }}
            />
          ) : (
            <button
              key={index}
              onClick={() => {
                setDraft(word.text)
                setEditing(index)
              }}
              title={formatTimecode(word.start)}
              className="mr-1 rounded-[2px] px-0.5 text-ink-200 transition-colors duration-150 hover:bg-sodium-700/25 hover:text-ink-100"
            >
              {word.text}
            </button>
          ),
        )}
      </div>

      <div className="mt-4 flex items-center gap-4">
        <button onClick={onSave} disabled={!dirty || saving} className="btn btn-ghost">
          {saving ? 'Saving…' : 'Save edits'}
        </button>
        <span className="text-xs text-ink-500">
          {dirty ? 'Unsaved changes' : 'Click any word to correct it'}
        </span>
      </div>
    </div>
  )
}
