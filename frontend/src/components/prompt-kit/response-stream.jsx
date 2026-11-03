import { useEffect, useState } from 'react'

/**
 * Lightweight NOVA adaptation of Agents Kit's ResponseStream typewriter API.
 * It animates a completed response locally; NOVA's backend remains responsible
 * for the actual model response and task execution.
 */
export function ResponseStream({
  textStream,
  mode = 'typewriter',
  speed = 20,
  className = '',
  onComplete,
  as = 'div',
  renderText,
}) {
  const [displayedText, setDisplayedText] = useState('')
  const text = typeof textStream === 'string' ? textStream : String(textStream ?? '')

  useEffect(() => {
    if (mode !== 'typewriter' || !text) {
      setDisplayedText(text)
      onComplete?.()
      return undefined
    }

    let cancelled = false
    let frame = 0
    let index = 0
    let lastFrame = 0
    const normalizedSpeed = Math.min(100, Math.max(1, Number(speed) || 20))
    const delay = Math.max(1, Math.round(100 / Math.sqrt(normalizedSpeed)))
    const chunkSize = normalizedSpeed < 25 ? 1 : Math.max(1, Math.round((normalizedSpeed - 25) / 10))
    setDisplayedText('')

    const tick = (timestamp) => {
      if (cancelled) return
      if (timestamp - lastFrame < delay) {
        frame = window.requestAnimationFrame(tick)
        return
      }
      lastFrame = timestamp
      index = Math.min(text.length, index + chunkSize)
      setDisplayedText(text.slice(0, index))
      if (index < text.length) {
        frame = window.requestAnimationFrame(tick)
      } else {
        onComplete?.()
      }
    }

    frame = window.requestAnimationFrame(tick)
    return () => {
      cancelled = true
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [text, mode, speed, onComplete])

  const Element = as
  const content = typeof renderText === 'function' ? renderText(displayedText) : displayedText
  return <Element className={className}>{content}</Element>
}

export default ResponseStream
