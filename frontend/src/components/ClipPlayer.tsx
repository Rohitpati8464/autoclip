import { useCallback, useEffect, useRef, useState } from 'react'

import { formatTimecode, type CaptionStyle, type Word } from '../api'

/**
 * 9:16 preview of one clip, with a CSS approximation of the burned captions.
 *
 * The approximation is deliberate: rendering the real ASS would mean shipping a
 * subtitle engine to the browser. What matters at review time is timing, word
 * grouping, and whether the style reads at all — the final look comes from
 * libass at export.
 */
export function ClipPlayer({
  src,
  startS,
  endS,
  words,
  style,
  ratio,
}: {
  src: string
  startS: number
  endS: number
  words: Word[]
  style: CaptionStyle | undefined
  ratio: string
}) {
  const video = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(startS)

  // Re-seek whenever the clip or its trim changes, so the preview always starts
  // where the export will.
  useEffect(() => {
    const element = video.current
    if (!element) return
    element.currentTime = startS
    setTime(startS)
    setPlaying(false)
    element.pause()
  }, [src, startS])

  const onTimeUpdate = useCallback(() => {
    const element = video.current
    if (!element) return
    if (element.currentTime >= endS) {
      element.pause()
      element.currentTime = startS
      setPlaying(false)
      setTime(startS)
      return
    }
    setTime(element.currentTime)
  }, [endS, startS])

  const toggle = () => {
    const element = video.current
    if (!element) return
    if (element.paused) {
      if (element.currentTime < startS || element.currentTime >= endS) {
        element.currentTime = startS
      }
      void element.play()
      setPlaying(true)
    } else {
      element.pause()
      setPlaying(false)
    }
  }

  const elapsed = Math.max(0, time - startS)
  const duration = Math.max(0.01, endS - startS)
  const aspect = ratio === '1:1' ? '1 / 1' : ratio === '16:9' ? '16 / 9' : '9 / 16'

  return (
    <div className="flex flex-col items-center">
      <div
        className="relative w-full overflow-hidden bg-ink-850"
        style={{ aspectRatio: aspect, maxHeight: '62vh' }}
        onClick={toggle}
        role="button"
        tabIndex={0}
        aria-label={playing ? 'Pause' : 'Play'}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            toggle()
          }
        }}
      >
        <video
          ref={video}
          src={src}
          className="size-full object-cover"
          onTimeUpdate={onTimeUpdate}
          preload="auto"
          playsInline
        />

        <CaptionOverlay words={words} time={time} style={style} />

        {!playing && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <span className="grid size-16 place-items-center rounded-full bg-ink-900/70 pl-1 text-2xl text-ink-100 backdrop-blur-[2px]">
              ▶
            </span>
          </div>
        )}
      </div>

      <div className="mt-3 flex w-full items-center gap-4">
        <button onClick={toggle} className="btn btn-quiet -ml-1 w-16 justify-start">
          {playing ? 'Pause' : 'Play'}
        </button>
        <div className="h-px flex-1 bg-ink-800">
          <div
            className="h-px origin-left bg-sodium-500"
            style={{ transform: `scaleX(${elapsed / duration})` }}
          />
        </div>
        <span className="numeric text-xs text-ink-500">
          {formatTimecode(elapsed)} / {formatTimecode(duration)}
        </span>
      </div>
    </div>
  )
}

/** Group words the way the ASS generator does, then show the active group. */
function CaptionOverlay({
  words,
  time,
  style,
}: {
  words: Word[]
  time: number
  style: CaptionStyle | undefined
}) {
  if (!style || words.length === 0) return null

  const groups = groupWords(words, style.preview.maxWords)
  const active = groups.find((group) => time >= group[0].start && time <= group[group.length - 1].end)
  if (!active) return null

  const { primary, accent, allCaps, outlineWidth, boxed, marginRatio, sizeRatio } = style.preview

  return (
    <div
      className="pointer-events-none absolute inset-x-0 flex justify-center px-[6%]"
      style={{ bottom: `${marginRatio * 100}%` }}
    >
      <p
        className="text-center leading-[1.15]"
        style={{
          fontFamily: style.preview.font === 'Anton' ? 'Anton, Impact, sans-serif' : undefined,
          fontSize: `clamp(0.75rem, ${sizeRatio * 100}cqh, 4rem)`,
          fontWeight: boxed || style.preview.font === 'Anton' ? 400 : 600,
          textTransform: allCaps ? 'uppercase' : 'none',
          color: primary,
          textShadow: boxed
            ? undefined
            : `0 0 ${outlineWidth}px #000, 0 0 ${outlineWidth * 2}px #000`,
          background: boxed ? 'rgba(0,0,0,0.78)' : undefined,
          padding: boxed ? '0.15em 0.4em' : undefined,
        }}
      >
        {active.map((word, index) => {
          const isActive = time >= word.start && time <= word.end
          return (
            <span
              key={`${word.start}-${index}`}
              style={{
                color: isActive && accent ? accent : undefined,
                display: 'inline-block',
                transform: isActive && accent ? 'scale(1.08)' : undefined,
                transition: 'transform 120ms cubic-bezier(0.16,1,0.3,1)',
                marginInline: '0.14em',
              }}
            >
              {allCaps ? word.text.toUpperCase() : word.text}
            </span>
          )
        })}
      </p>
    </div>
  )
}

function groupWords(words: Word[], maxWords: number): Word[][] {
  const groups: Word[][] = []
  let current: Word[] = []

  for (const [index, word] of words.entries()) {
    if (current.length > 0) {
      const gap = word.start - current[current.length - 1].end
      if (gap > 0.4 || current.length >= maxWords) {
        groups.push(current)
        current = []
      }
    }
    current.push(word)
    if (/[.!?…]$/.test(word.text.trim()) && index !== words.length - 1) {
      groups.push(current)
      current = []
    }
  }
  if (current.length > 0) groups.push(current)
  return groups
}
