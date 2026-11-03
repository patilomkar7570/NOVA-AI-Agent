import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import heroPhoto from './assets/nova-hero-photo.png'
import { startWavBackup, startMicLevelMonitor, transcribeWithVoicebox } from './voice/voiceController.js'
import { createVoicePlaybackQueue } from './voice/voicePlaybackQueue.js'
import { startVoiceActivityCapture, transcribeVoiceSegment } from './voice/voiceActivityController.js'
import { getVoiceOrbState, getVoiceStatusLabel } from './voice/voiceUiState.js'
import { NOVA_CONVERSATION_LANGUAGES, normalizeConversationLanguage, getBrowserRecognitionLocale, detectConversationLanguage, normalizeNOVAAssistantNameTranscript } from './voice/conversationLanguage.js'
import { ensureBrowserOnDeviceRecognition, getBrowserOnDeviceRecognitionLocales, getBrowserSpeechRecognitionConstructor } from './voice/browserSpeechRecognition.js'
import { MercuryOrb } from './components/voiceorbs/orbe/mercury-orb'
import { ResponseStream } from './components/prompt-kit/response-stream.jsx'


const ACCENT_THEMES = [
  { id: 'sage', name: 'Sage', primary: '#58776c', hover: '#4e6e63', light: '#a4b9ae', highlight: '#b2c7bc', soft: '#e5ece7', sidebar: '#dfe3da', curveBack: '#cdd4ca', curveFront: '#bfc9c0' },
  { id: 'ocean', name: 'Ocean', primary: '#386f9f', hover: '#2d5f89', light: '#a7c1d9', highlight: '#b8cde1', soft: '#e5eef7', sidebar: '#dce7f1', curveBack: '#c7d8e8', curveFront: '#b6cadd' },
  { id: 'violet', name: 'Violet', primary: '#7055a5', hover: '#5e478d', light: '#b7acd3', highlight: '#c8bee0', soft: '#eee9f7', sidebar: '#e7e1f0', curveBack: '#d6cde6', curveFront: '#c7badd' },
  { id: 'rose', name: 'Rose', primary: '#a95770', hover: '#91465d', light: '#d6a9b7', highlight: '#e2bbc7', soft: '#f7e8ed', sidebar: '#f0dfe5', curveBack: '#e5cbd4', curveFront: '#dcbcc9' },
  { id: 'amber', name: 'Amber', primary: '#a9772f', hover: '#8c6124', light: '#d3b782', highlight: '#e1caa0', soft: '#f5eedf', sidebar: '#eee5d2', curveBack: '#e1d3b7', curveFront: '#d8c7a4' },
  { id: 'teal', name: 'Teal', primary: '#247e7b', hover: '#176a67', light: '#9fc8c4', highlight: '#b5dad5', soft: '#e0f0ee', sidebar: '#d9eae6', curveBack: '#c0dbd5', curveFront: '#afd0c7' },
  { id: 'graphite', name: 'Graphite', primary: '#536575', hover: '#414f5d', light: '#aebcc8', highlight: '#c1ccd5', soft: '#e8edf1', sidebar: '#dfe5e9', curveBack: '#cbd5dc', curveFront: '#bac7d0' },
]

function SendArrowIcon() {
  return (
    <svg width="23" height="23" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 19V5M6.5 10.5 12 5l5.5 5.5" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function StopSquareIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="6.5" y="6.5" width="11" height="11" rx="1.8" fill="currentColor" />
    </svg>
  )
}

function VoiceBars({ levels, active = false }) {
  const values = levels?.length ? levels : Array(28).fill(0.02)
  return (
    <div
      className={`voice-capture-waveform ${active ? 'is-active' : ''}`}
      aria-label={active ? 'Live microphone waveform' : 'Microphone waveform'}
      role="img"
      aria-live="off"
    >
      {values.map((level, index) => {
        const normalized = Math.max(0, Math.min(1, Number(level) || 0))
        const height = 4 + Math.pow(normalized, 0.72) * 25
        return (
          <span
            key={index}
            className="voice-capture-bar"
            style={{ height: `${height.toFixed(1)}px`, animationDelay: `${index * -37}ms` }}
          />
        )
      })}
    </div>
  )
}

function MicIcon() {
  return (
    <svg
      width="21"
      height="21"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
      <path d="M12 17.5V21" />
      <path d="M8.5 21h7" />
    </svg>
  )
}

function VoiceRetryIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M20 7v5h-5M4.9 9a7.5 7.5 0 0 1 13.2-2L20 12M4 17v-5h5m10.1 3a7.5 7.5 0 0 1-13.2 2L4 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function VoiceModeIcon() {
  return (
    <svg width="23" height="23" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4.5 10v4M8.25 6.5v11M12 3.5v17M15.75 6.5v11M19.5 10v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function CaptionsIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="3" />
      <path d="M7 10.5h4m-4 3h2m4-3h4m-4 3h2" />
    </svg>
  )
}



function HomeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
      <path d="M9.5 21v-6h5v6" />
    </svg>
  )
}

function NewChatIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true">
      <path d="M5 4.75h10.5A3.75 3.75 0 0 1 19.25 8.5V16A3.25 3.25 0 0 1 16 19.25H8l-4.25 2v-16.5Z" />
      <path d="M12 8.5v6M9 11.5h6" />
    </svg>
  )
}

function CopyResponseIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="8" y="8" width="12" height="12" rx="2" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </svg>
  )
}

function ReadAloudIcon({ active = false }) {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 10v4h3l4 3V7l-4 3H4Z" />
      {active ? <><path d="M16 9v6M20 9v6" /></> : <><path d="M15 9a4 4 0 0 1 0 6" /><path d="M17.5 6.5a8 8 0 0 1 0 11" /></>}
    </svg>
  )
}

function GlowingEffect({ proximity = 80, borderWidth = 1.35, halo = true, arcLength = 120 }) {
  const ref = useRef(null)
  const svgRef = useRef(null)
  const pathRef = useRef(null)
  const haloPathRef = useRef(null)

  useEffect(() => {
    const element = ref.current
    const svg = svgRef.current
    const path = pathRef.current
    const haloPath = haloPathRef.current
    const host = element?.parentElement
    if (!element || !svg || !path || !host) return undefined

    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (reduceMotion?.matches) return undefined

    const OFF = -100000
    let pointerX = OFF
    let pointerY = OFF
    let currentDistance = null
    let totalLength = 0
    let sampleCount = 0
    let animationFrame = 0
    let observing = false

    const setRectGeometry = () => {
      const rect = host.getBoundingClientRect()
      const width = Math.max(0, rect.width)
      const height = Math.max(0, rect.height)
      if (width < 2 || height < 2) return

      const styles = window.getComputedStyle(host)
      const radiusValue = parseFloat(styles.borderTopLeftRadius) || 0
      const inset = Math.max(0.65, borderWidth / 2 + 0.35)
      const rx = Math.max(0, Math.min(radiusValue - inset, (height - inset * 2) / 2, (width - inset * 2) / 2))

      svg.setAttribute('viewBox', `0 0 ${width} ${height}`)
      svg.setAttribute('width', String(width))
      svg.setAttribute('height', String(height))
      path.setAttribute('x', String(inset))
      path.setAttribute('y', String(inset))
      path.setAttribute('width', String(Math.max(1, width - inset * 2)))
      path.setAttribute('height', String(Math.max(1, height - inset * 2)))
      path.setAttribute('rx', String(rx))
      path.setAttribute('ry', String(rx))
      path.setAttribute('stroke-width', String(borderWidth))

      if (haloPath) {
        haloPath.setAttribute('x', String(inset))
        haloPath.setAttribute('y', String(inset))
        haloPath.setAttribute('width', String(Math.max(1, width - inset * 2)))
        haloPath.setAttribute('height', String(Math.max(1, height - inset * 2)))
        haloPath.setAttribute('rx', String(rx))
        haloPath.setAttribute('ry', String(rx))
        haloPath.setAttribute('stroke-width', String(borderWidth + 5))
      }

      totalLength = path.getTotalLength()
      if (!Number.isFinite(totalLength) || totalLength <= 0) return
      // One dash plus one gap adds up to exactly one full perimeter. This
      // makes the pattern seam line up perfectly when the segment crosses
      // the closed path's start/end point.
      const visibleLength = Math.min(arcLength, totalLength * 0.42)
      const dash = `${visibleLength} ${Math.max(0.01, totalLength - visibleLength)}`
      path.style.strokeDasharray = dash
      if (haloPath) haloPath.style.strokeDasharray = dash
      sampleCount = Math.max(120, Math.min(360, Math.ceil(totalLength / 3)))
    }

    const findNearestPerimeterDistance = () => {
      if (!totalLength || !sampleCount) return null
      const matrix = svg.getScreenCTM()
      if (!matrix) return null
      let localPointer
      try {
        localPointer = new DOMPoint(pointerX, pointerY).matrixTransform(matrix.inverse())
      } catch {
        return null
      }

      let bestDistanceSquared = Infinity
      let bestLength = 0
      for (let i = 0; i < sampleCount; i += 1) {
        const along = (totalLength * i) / sampleCount
        const point = path.getPointAtLength(along)
        const dx = point.x - localPointer.x
        const dy = point.y - localPointer.y
        const distanceSquared = dx * dx + dy * dy
        if (distanceSquared < bestDistanceSquared) {
          bestDistanceSquared = distanceSquared
          bestLength = along
        }
      }
      return bestLength
    }

    const update = () => {
      animationFrame = 0
      const rect = host.getBoundingClientRect()
      const dx = Math.max(rect.left - pointerX, 0, pointerX - rect.right)
      const dy = Math.max(rect.top - pointerY, 0, pointerY - rect.bottom)
      const opacity = Math.max(0, 1 - Math.hypot(dx, dy) / Math.max(proximity, 1))
      element.style.setProperty('--nova-glow-opacity', opacity.toFixed(3))

      if (!opacity) {
        currentDistance = null
        return
      }

      const targetDistance = findNearestPerimeterDistance()
      if (targetDistance === null) return

      if (currentDistance === null) {
        currentDistance = targetDistance
      } else {
        // Smooth along the actual perimeter distance, not a polar angle.
        // This keeps the lit segment's physical length identical everywhere.
        let delta = targetDistance - currentDistance
        delta = ((delta + totalLength / 2) % totalLength + totalLength) % totalLength - totalLength / 2
        currentDistance = (currentDistance + delta * 0.28 + totalLength) % totalLength
        if (Math.abs(delta) > 0.35) animationFrame = window.requestAnimationFrame(update)
      }

      const visibleLength = Math.min(arcLength, totalLength * 0.42)
      const offset = -(currentDistance - visibleLength / 2)
      path.style.strokeDashoffset = String(offset)
      if (haloPath) haloPath.style.strokeDashoffset = String(offset)
    }

    const queueUpdate = () => {
      if (!animationFrame) animationFrame = window.requestAnimationFrame(update)
    }
    const onPointerMove = (event) => {
      if (event.pointerType === 'touch') return
      pointerX = event.clientX
      pointerY = event.clientY
      queueUpdate()
    }
    const onPointerOut = (event) => {
      if (event.relatedTarget) return
      pointerX = OFF
      pointerY = OFF
      queueUpdate()
    }
    const onWindowBlur = () => {
      pointerX = OFF
      pointerY = OFF
      queueUpdate()
    }
    const listen = (enabled) => {
      if (enabled === observing) return
      observing = enabled
      if (enabled) {
        document.addEventListener('pointermove', onPointerMove, { passive: true })
        document.addEventListener('pointerout', onPointerOut)
        window.addEventListener('blur', onWindowBlur)
        window.addEventListener('scroll', queueUpdate, { passive: true })
        setRectGeometry()
        queueUpdate()
      } else {
        document.removeEventListener('pointermove', onPointerMove)
        document.removeEventListener('pointerout', onPointerOut)
        window.removeEventListener('blur', onWindowBlur)
        window.removeEventListener('scroll', queueUpdate)
      }
    }

    let intersectionObserver
    if ('IntersectionObserver' in window) {
      intersectionObserver = new IntersectionObserver((entries) => {
        const entry = entries[entries.length - 1]
        listen(Boolean(entry?.isIntersecting))
      })
      intersectionObserver.observe(element)
    } else {
      listen(true)
    }

    const resizeObserver = 'ResizeObserver' in window
      ? new ResizeObserver(() => { setRectGeometry(); queueUpdate() })
      : null
    resizeObserver?.observe(host)
    setRectGeometry()

    return () => {
      intersectionObserver?.disconnect()
      resizeObserver?.disconnect()
      listen(false)
      if (animationFrame) window.cancelAnimationFrame(animationFrame)
    }
  }, [proximity, borderWidth, arcLength])

  return (
    <span ref={ref} className="nova-glowing-effect" aria-hidden="true" style={{ '--nova-glow-border-width': `${borderWidth}px` }}>
      <svg ref={svgRef} className="nova-glow-svg" preserveAspectRatio="none" aria-hidden="true">
        {halo && <rect ref={haloPathRef} className="nova-glow-halo-path" fill="none" />}
        <rect ref={pathRef} className="nova-glow-path" fill="none" />
      </svg>
    </span>
  )
}

function SettingsIcon() {
  return (
    <svg
      className="nova-settings-gear-icon"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.35"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543-.94 3.465.982 2.525 2.525a1.724 1.724 0 0 0 1.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 0 0-1.066 2.573c.94 1.543-.982 3.465-2.525 2.525a1.724 1.724 0 0 0-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 0 0-2.573-1.066c-1.543.94-3.465-.982-2.525-2.525a1.724 1.724 0 0 0-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 0 0 1.066-2.573c-.94-1.543.982-3.465 2.525-2.525a1.724 1.724 0 0 0 2.573-1.066z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function FolderIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <path d="M3.5 7.5A2.5 2.5 0 0 1 6 5h4l2 2h6.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <path d="M6 3.5h8l4 4V20H6z" />
      <path d="M14 3.5V8h4" />
    </svg>
  )
}

function CalendarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <rect x="4" y="5" width="16" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M4 10h16" />
    </svg>
  )
}

function GridIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </svg>
  )
}


function SearchIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="10.8" cy="10.8" r="6.8" />
      <path d="m16 16 4.2 4.2" />
    </svg>
  )
}

function VoiceProfilePicker({ profiles, value, onValueChange, onPreview, onOpen, previewingId = '', loading = false, error = '' }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const pickerRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const closeOnOutsidePointer = (event) => {
      if (!pickerRef.current?.contains(event.target)) setOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', closeOnOutsidePointer, true)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePointer, true)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])
  const selected = profiles.find((profile) => String(profile.id) === String(value))
  const filtered = profiles.filter((profile) => {
    const haystack = `${profile.name || ''} ${profile.description || ''} ${profile.language || ''} ${profile.voice_type || ''} ${profile.preset_engine || ''}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })

  return (
    <div className="nova-voice-picker" ref={pickerRef}>
      <button
        type="button"
        className="nova-voice-picker-trigger"
        onClick={() => {
          const nextOpen = !open
          setOpen(nextOpen)
          if (nextOpen) void onOpen?.()
        }}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className="nova-voice-picker-selected-mark" aria-hidden="true"><i /></span>
        <span className="nova-voice-picker-trigger-copy">
          <strong>{selected?.name || (loading ? 'Loading Voicebox voices…' : 'Choose a voice')}</strong>
          <small>{selected ? `${selected.language || 'en'} · ${selected.voice_type || 'voice profile'}` : 'Select a Voicebox profile'}</small>
        </span>
        <span className="nova-voice-picker-chevron" aria-hidden="true">⌄</span>
      </button>

      {open && (
        <div className="nova-voice-picker-popover">
          <div className="nova-voice-picker-search">
            <SearchIcon />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search voices…"
              aria-label="Search Voicebox voices"
              autoFocus
            />
          </div>
          {error && <p className="nova-voice-picker-error" role="status">{error}</p>}
          {!loading && !filtered.length && <p className="nova-voice-picker-empty">{profiles.length ? 'No matching voice profiles.' : 'No voice profiles are available yet.'}</p>}
          {!loading && !profiles.length && (
            <button type="button" className="nova-voice-picker-retry" onClick={() => void onOpen?.()}>
              Retry Voicebox connection
            </button>
          )}
          <div className="nova-voice-picker-list" role="listbox" aria-label="Available Voicebox voices">
            {filtered.map((profile) => {
              const selectedProfile = String(profile.id) === String(value)
              const isPreviewing = previewingId === String(profile.id)
              return (
                <div className={`nova-voice-picker-row ${selectedProfile ? 'selected' : ''}`} key={profile.id}>
                  <button
                    type="button"
                    className="nova-voice-picker-choice"
                    role="option"
                    aria-selected={selectedProfile}
                    onClick={() => { onValueChange(profile.id); setOpen(false) }}
                  >
                    <span className="nova-voice-picker-orb" aria-hidden="true"><i /></span>
                    <span className="nova-voice-picker-profile-copy">
                      <strong>{profile.name || 'Voice profile'}</strong>
                      <small>{[profile.language || 'en', profile.voice_type || 'voice profile', profile.preset_engine].filter(Boolean).join(' · ')}</small>
                    </span>
                    <span className="nova-voice-picker-check" aria-hidden="true">{selectedProfile ? '✓' : ''}</span>
                  </button>
                  <button
                    type="button"
                    className={`nova-voice-picker-preview ${isPreviewing ? 'is-playing' : ''}`}
                    onClick={() => onPreview(profile)}
                    aria-label={`${isPreviewing ? 'Stop preview of' : 'Preview'} ${profile.name || 'voice'}`}
                    title={isPreviewing ? 'Stop preview' : 'Preview voice'}
                  >
                    {isPreviewing ? 'Ⅱ' : '▶'}
                  </button>
                </div>
              )
            })}
          </div>
          <div className="nova-voice-picker-footnote">Voices are loaded from your local Voicebox profiles.</div>
        </div>
      )}
    </div>
  )
}

function renderMessageContent(content) {
  const text = String(content || '')
  const pattern = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|\*\*(.+?)\*\*/g
  const nodes = []
  let cursor = 0
  let match

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) nodes.push(<span key={`text-${cursor}`}>{text.slice(cursor, match.index)}</span>)
    if (match[1] && match[2]) {
      nodes.push(
        <a key={`link-${match.index}`} href={match[2]} target="_blank" rel="noreferrer">
          {match[1]}
        </a>
      )
    } else if (match[3]) {
      nodes.push(<strong key={`bold-${match.index}`}>{match[3]}</strong>)
    }
    cursor = pattern.lastIndex
  }

  if (cursor < text.length) nodes.push(<span key={`text-${cursor}`}>{text.slice(cursor)}</span>)
  return nodes
}

function compareEventIds(left, right) {
  const a = String(left ?? '0')
  const b = String(right ?? '0')
  if (a.length !== b.length) return a.length - b.length
  return a.localeCompare(b)
}

function describeActivityEvent(event) {
  const message = String(event?.message || '').trim()
  const kind = String(event?.kind || '').toLowerCase()
  const eventName = String(event?.event || '').toLowerCase()
  if (kind === 'approval_required' || /waiting for explicit user approval/i.test(message)) {
    return 'Waiting for your approval'
  }
  if (/router: request validated|intent analysed|accepted plan|planning/i.test(message) || /plan|route/.test(eventName)) {
    return 'Understanding your request and preparing a plan'
  }
  if (/searching/i.test(message) || /search/.test(eventName)) {
    return 'Searching for relevant information'
  }
  if (/inspecting|reading|opening/i.test(message) || /inspect|browse|navigate|open/.test(eventName)) {
    return 'Opening and reading relevant sources'
  }
  if (/synthesising|synthesizing|combining|summaris|summariz/i.test(message) || /synth|summar/.test(eventName)) {
    return 'Organising the information into an answer'
  }
  if (/verif|check|validat/i.test(message) || /verif|check|validat/.test(eventName)) {
    return 'Checking the results'
  }
  if (kind === 'done' || eventName === 'task_result') return 'Finishing your response'
  if (kind === 'error' || kind === 'warning') return 'Working through a temporary issue'
  if (message.startsWith('Running:')) return 'Starting your request'
  return 'Working through your request'
}


function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('nova-sidebar-collapsed') === 'true')

  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('nova-sidebar-width')
    return saved ? Number(saved) : 207
  })

const [task, setTask] = useState('')
  const [taskStarting, setTaskStarting] = useState(false)
  const taskSubmissionRef = useRef(false)
  const activeTaskIdRef = useRef(null)
  const [activityMessage, setActivityMessage] = useState('Ready for your next request.')
  const [activityAgent, setActivityAgent] = useState('')
  const activityEventCursorRef = useRef('0')
  const [listening, setListening] = useState(false)
  const [localRetryAvailable, setLocalRetryAvailable] = useState(false)
  const [localTranscribing, setLocalTranscribing] = useState(false)
  const [voiceNotice, setVoiceNotice] = useState('')
  const [voiceTranscriptReady, setVoiceTranscriptReady] = useState(false)
  const [voiceLiveTranscript, setVoiceLiveTranscript] = useState('')
  const [voiceLevels, setVoiceLevels] = useState(() => Array(28).fill(0.015))
  const [voiceRecognitionMode, setVoiceRecognitionMode] = useState(() => {
    const saved = localStorage.getItem('nova-voice-recognition-mode')
    return ['auto', 'local', 'online'].includes(saved) ? saved : 'auto'
  })
  const recognitionRef = useRef(null)
  const voiceBackupRef = useRef(null)
  const voiceRetryAudioRef = useRef(null)
  const voiceLevelMonitorRef = useRef(null)
  const voiceRecognitionFailedRef = useRef(false)
  const activeVoiceInputModeRef = useRef(null)
  const [activeVoiceInputMode, setActiveVoiceInputMode] = useState(null)
  const autoFallbackStartedRef = useRef(false)

  // Full-screen Voice Mode uses a single local microphone stream for the orb
  // meter and continuous VAD. Only completed speech segments are sent to the
  // existing local Voicebox transcription endpoint.
  const [voiceModeOpen, setVoiceModeOpen] = useState(false)
  const voiceModeOpenRef = useRef(false)
  const [voiceModeMicEnabled, setVoiceModeMicEnabled] = useState(true)
  const [voiceCaptionsEnabled, setVoiceCaptionsEnabled] = useState(() => localStorage.getItem('nova-voice-captions-enabled') !== 'false')
  const [voiceContinuousEnabled, setVoiceContinuousEnabled] = useState(() => localStorage.getItem('nova-voice-continuous-enabled') !== 'false')
  const [voiceAutomaticInterruptionEnabled, setVoiceAutomaticInterruptionEnabled] = useState(() => localStorage.getItem('nova-voice-auto-interruption') !== 'false')
  const [voiceSpeechSpeed, setVoiceSpeechSpeed] = useState(() => { const saved = Number(localStorage.getItem('nova-voice-speech-speed')); return Number.isFinite(saved) && saved >= 0.8 && saved <= 1.25 ? saved : 1 })
  const [voiceCaptureRetryNonce, setVoiceCaptureRetryNonce] = useState(0)
  const [voiceModeTranscript, setVoiceModeTranscript] = useState('')
  const [voiceModeAssistantTranscript, setVoiceModeAssistantTranscript] = useState('')
  const [voiceModeTurns, setVoiceModeTurns] = useState([])
  const voiceTranscriptEndRef = useRef(null)
  const [voiceModeCaptionError, setVoiceModeCaptionError] = useState('')
  const [voiceRoomStatus, setVoiceRoomStatus] = useState('idle')
  const voiceModeMicEnabledRef = useRef(true)
  const voiceContinuousEnabledRef = useRef(true)
  const voiceAutomaticInterruptionEnabledRef = useRef(true)
  const voiceModeStreamRef = useRef(null)
  const voiceModeAudioContextRef = useRef(null)
  const voiceOrbLevelRef = useRef(-1)
  const voiceActivityCaptureRef = useRef(null)
  const voiceModeRecognitionRef = useRef(null)
  const voiceModeRecognitionStartRef = useRef(null)
  const voiceModeBrowserRecognitionActiveRef = useRef(false)
  const voiceModeBrowserFinalTranscriptRef = useRef('')
  const voiceModeBrowserInterimTranscriptRef = useRef('')
  const voiceModeRecognitionRestartTimerRef = useRef(null)
  const voiceAutoSubmitLockRef = useRef(false)
  const voicePendingUtterancesRef = useRef([])
  const voiceInterruptionPendingRef = useRef(false)
  const runTaskRef = useRef(null)

  // Keep the mutable control-flow ref and render-visible state in sync.
  // Refs remain useful inside async callbacks; JSX reads the state snapshot.
  const updateActiveVoiceInputMode = (mode) => {
    activeVoiceInputModeRef.current = mode
    setActiveVoiceInputMode(mode)
  }
  const [activeSection, setActiveSection] = useState('home')
  const [userName, setUserName] = useState(() => localStorage.getItem('nova-user-name') || 'Omkar')
  const [nameDraft, setNameDraft] = useState(() => localStorage.getItem('nova-user-name') || 'Omkar')
  const [running, setRunning] = useState(false)
  const [pendingApproval, setPendingApproval] = useState(null)
  const [approvalBusy, setApprovalBusy] = useState(false)
  const [stopArmed, setStopArmed] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)
  const [systemSnapshot, setSystemSnapshot] = useState(null)
  const [statusMessage, setStatusMessage] = useState('')
  const [copiedMessageKey, setCopiedMessageKey] = useState('')
  const [speakingMessageKey, setSpeakingMessageKey] = useState('')
  const [speechBusyMessageKey, setSpeechBusyMessageKey] = useState('')
  const [speechError, setSpeechError] = useState('')
  const speechAudioContextRef = useRef(null)
  const speechSourceRef = useRef(null)
  const speechRequestControllerRef = useRef(null)
  const speechPlaybackTokenRef = useRef(0)
  const voicePlaybackQueueRef = useRef(null)
  const voiceModeStreamedTextRef = useRef('')
  const voiceStreamSessionCancelledRef = useRef(false)
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const chatRevisionRef = useRef(0)
  const conversationMessagesRef = useRef(null)

  const [themeMode, setThemeMode] = useState(() => {
    const saved = localStorage.getItem('nova-theme')
    return ['light', 'dark', 'system'].includes(saved) ? saved : 'system'
  })
  const [accentTheme, setAccentTheme] = useState(() => {
    const saved = localStorage.getItem('nova-accent-theme')
    return ACCENT_THEMES.some((theme) => theme.id === saved) ? saved : 'sage'
  })
  const [conversationLanguage, setConversationLanguage] = useState(() => normalizeConversationLanguage(localStorage.getItem('nova-conversation-language'), 'en'))
  const [settingsTab, setSettingsTab] = useState('display')
  const [chatSearchOpen, setChatSearchOpen] = useState(false)
  const [chatSearchQuery, setChatSearchQuery] = useState('')
  const [voiceProfiles, setVoiceProfiles] = useState([])
  const [voiceProfilesLoading, setVoiceProfilesLoading] = useState(false)
  const [voiceProfilesError, setVoiceProfilesError] = useState('')
  const [selectedVoiceProfileId, setSelectedVoiceProfileId] = useState(() => localStorage.getItem('nova-voice-profile-id') || '')
  const [speakVoiceCommandReplies, setSpeakVoiceCommandReplies] = useState(() => localStorage.getItem('nova-speak-voice-command-replies-v2') !== 'false')
  const [typewriterTarget, setTypewriterTarget] = useState(null)
  const selectedAccent = ACCENT_THEMES.find((theme) => theme.id === accentTheme) || ACCENT_THEMES[0]
  const voiceOrbState = getVoiceOrbState(voiceRoomStatus, voiceModeMicEnabled)
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)
  const darkMode = themeMode === 'dark' || (themeMode === 'system' && systemDark)

  useEffect(() => {
    localStorage.setItem('nova-theme', themeMode)
  }, [themeMode])

  useEffect(() => {
    localStorage.setItem('nova-accent-theme', accentTheme)
  }, [accentTheme])

  useEffect(() => {
    localStorage.setItem('nova-conversation-language', conversationLanguage)
  }, [conversationLanguage])

  useEffect(() => {
    localStorage.setItem('nova-voice-recognition-mode', voiceRecognitionMode)
  }, [voiceRecognitionMode])

  useEffect(() => {
    if (selectedVoiceProfileId) localStorage.setItem('nova-voice-profile-id', selectedVoiceProfileId)
  }, [selectedVoiceProfileId])

  useEffect(() => {
    localStorage.setItem('nova-speak-voice-command-replies-v2', String(speakVoiceCommandReplies))
  }, [speakVoiceCommandReplies])

  useEffect(() => {
    localStorage.setItem('nova-voice-captions-enabled', String(voiceCaptionsEnabled))
  }, [voiceCaptionsEnabled])

  useEffect(() => {
    localStorage.setItem('nova-voice-continuous-enabled', String(voiceContinuousEnabled))
    voiceContinuousEnabledRef.current = voiceContinuousEnabled
  }, [voiceContinuousEnabled])

  useEffect(() => {
    localStorage.setItem('nova-voice-auto-interruption', String(voiceAutomaticInterruptionEnabled))
    voiceAutomaticInterruptionEnabledRef.current = voiceAutomaticInterruptionEnabled
  }, [voiceAutomaticInterruptionEnabled])

  useEffect(() => {
    localStorage.setItem('nova-voice-speech-speed', String(voiceSpeechSpeed))
  }, [voiceSpeechSpeed])

  useEffect(() => {
    if (voiceModeOpen && voiceCaptionsEnabled) {
      voiceTranscriptEndRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
    }
  }, [voiceModeOpen, voiceCaptionsEnabled, voiceModeTurns, voiceModeTranscript, voiceModeAssistantTranscript])

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!media) return
    const updateSystemTheme = (event) => setSystemDark(event.matches)
    media.addEventListener?.('change', updateSystemTheme)
    return () => media.removeEventListener?.('change', updateSystemTheme)
  }, [])

  useEffect(() => {
    localStorage.setItem('nova-sidebar-width', sidebarWidth)
  }, [sidebarWidth])

  useEffect(() => {
    localStorage.setItem('nova-sidebar-collapsed', sidebarCollapsed)
  }, [sidebarCollapsed])

  const loadVoiceProfiles = useCallback(async () => {
    setVoiceProfilesLoading(true)
    setVoiceProfilesError('')
    try {
      const response = await fetch('http://127.0.0.1:8000/api/voice/profiles', { cache: 'no-store' })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        const detail = payload.detail ? ` ${typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)}` : ''
        throw new Error(`${payload.error || `Voicebox voice list failed (HTTP ${response.status}).`}${detail}`)
      }
      const profiles = Array.isArray(payload.profiles) ? payload.profiles : []
      setVoiceProfiles(profiles)
      const savedId = localStorage.getItem('nova-voice-profile-id') || ''
      const selectedExists = profiles.some((profile) => String(profile.id) === String(savedId))
      const fallback = profiles.find((profile) => profile.is_default || profile.default) || profiles[0]
      if (!selectedExists && fallback?.id) setSelectedVoiceProfileId(String(fallback.id))
      else if (!profiles.length) {
        setSelectedVoiceProfileId('')
        localStorage.removeItem('nova-voice-profile-id')
        setVoiceProfilesError('Voicebox is reachable, but it returned no voice profiles. Create or import a voice in Voicebox, then retry.')
      }
      return profiles
    } catch (error) {
      setVoiceProfiles([])
      setSelectedVoiceProfileId('')
      localStorage.removeItem('nova-voice-profile-id')
      setVoiceProfilesError(error instanceof Error ? error.message : 'Could not connect to Voicebox. Start Voicebox and retry.')
      return []
    } finally {
      setVoiceProfilesLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadVoiceProfiles()
  }, [loadVoiceProfiles])

  // Best-effort Voicebox Whisper warm-up. There is deliberately no settings
  // status card: a failed optional preload must never look like STT is broken.
  useEffect(() => {
    const warmVoiceboxWhisper = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/voice/whisper/preload', {
          method: 'POST',
          cache: 'no-store',
        })
        if (!response.ok) return
      } catch {
        // Voicebox can still load Whisper when a transcription is requested.
      }
    }
    void warmVoiceboxWhisper()
  }, [])

  const copyResponse = async (content, messageKey) => {
    const text = String(content || '').trim()
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const temporary = document.createElement('textarea')
      temporary.value = text
      temporary.setAttribute('readonly', '')
      temporary.style.position = 'fixed'
      temporary.style.opacity = '0'
      document.body.appendChild(temporary)
      temporary.select()
      const copied = document.execCommand('copy')
      temporary.remove()
      if (!copied) {
        setSpeechError('Could not copy this response in the current browser.')
        return
      }
    }
    setCopiedMessageKey(messageKey)
    window.setTimeout(() => setCopiedMessageKey((current) => current === messageKey ? '' : current), 1500)
  }

  const stopReadAloud = () => {
    speechPlaybackTokenRef.current += 1
    speechRequestControllerRef.current?.abort?.()
    speechRequestControllerRef.current = null

    const queue = voicePlaybackQueueRef.current
    voicePlaybackQueueRef.current = null
    queue?.dispose?.()

    const source = speechSourceRef.current
    speechSourceRef.current = null
    if (source) {
      source.onended = null
      try { source.stop() } catch { /* source may already have ended */ }
      try { source.disconnect() } catch { /* ignored */ }
    }

    setSpeakingMessageKey('')
    setSpeechBusyMessageKey('')
    if (voiceModeOpen) setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'listening' : 'muted')
  }

  const readAloudResponse = async (
    content,
    messageKey,
    profileIdOverride = selectedVoiceProfileId,
    streaming = false,
    languageOverride = null,
  ) => {
    if (speakingMessageKey === messageKey || speechBusyMessageKey === messageKey) {
      stopReadAloud()
      return
    }

    stopReadAloud()
    const playbackToken = speechPlaybackTokenRef.current
    const speechText = String(content || '').trim()
    if (!speechText && !streaming) return

    setSpeechError('')
    setSpeechBusyMessageKey(messageKey)
    if (voiceModeOpen) {
      setVoiceRoomStatus('thinking')
      setVoiceModeAssistantTranscript(speechText)
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    if (!AudioContextClass) {
      const error = new Error('Audio playback is not available in this browser.')
      setSpeechError(error.message)
      setSpeechBusyMessageKey('')
      if (voiceModeOpen) setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'listening' : 'muted')
      return
    }

    try {
      let audioContext = speechAudioContextRef.current
      if (!audioContext || audioContext.state === 'closed') {
        audioContext = new AudioContextClass()
        speechAudioContextRef.current = audioContext
      }
      // Start/resume from the active Voice Mode gesture. The queue is installed
      // before the first await so fast model tokens cannot outrun the TTS input.
      const audioReady = audioContext.state === 'suspended'
        ? audioContext.resume()
        : Promise.resolve()

      const queue = createVoicePlaybackQueue({
        audioContext,
        profileId: profileIdOverride,
        language: languageOverride || (conversationLanguage === 'auto'
          ? detectConversationLanguage(speechText, 'auto')
          : conversationLanguage),
        playbackRate: voiceSpeechSpeed,
        onState: (state) => {
          if (speechPlaybackTokenRef.current !== playbackToken) return
          if (state === 'generating') {
            setSpeechBusyMessageKey((current) => current || messageKey)
            if (voiceModeOpen && !voicePlaybackQueueRef.current?.isPlaying?.()) {
              setVoiceRoomStatus('thinking')
            }
          } else if (state === 'speaking') {
            setSpeechBusyMessageKey('')
            setSpeakingMessageKey(messageKey)
            if (voiceModeOpen) setVoiceRoomStatus('speaking')
          } else if (state === 'paused') {
            if (voiceModeOpen) setVoiceRoomStatus('paused')
          } else if (state === 'complete' || state === 'cancelled') {
            setSpeechBusyMessageKey('')
            setSpeakingMessageKey('')
            if (voiceModeOpen) setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'listening' : 'muted')
          }
        },
        onError: (error) => {
          if (speechPlaybackTokenRef.current !== playbackToken) return
          const message = error instanceof Error ? error.message : 'Could not read this response aloud.'
          setSpeechError(message)
          setSpeechBusyMessageKey('')
          setSpeakingMessageKey('')
          if (voiceModeOpen) {
            setVoiceModeCaptionError(message)
            setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'ready' : 'muted')
          }
        },
      })
      voicePlaybackQueueRef.current = queue

      const completion = streaming ? queue.startStreaming() : queue.start(speechText)
      await audioReady
      if (speechPlaybackTokenRef.current !== playbackToken) return
      await completion
    } catch (error) {
      if (speechPlaybackTokenRef.current !== playbackToken) return
      console.error('NOVA sentence audio queue:', error)
      const message = error instanceof Error ? error.message : 'Could not read this response aloud.'
      setSpeechError(message)
      if (voiceModeOpen) {
        setVoiceModeCaptionError(message)
        setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'ready' : 'muted')
      }
    } finally {
      if (speechPlaybackTokenRef.current === playbackToken) {
        setSpeechBusyMessageKey('')
        setSpeakingMessageKey('')
        if (voiceModeOpen) setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'listening' : 'muted')
      }
    }
  }

  const previewVoiceProfile = (profile) => {
    if (!profile?.id) return
    void readAloudResponse('Hello, I am NOVA. This is a short preview of the selected voice.', `voice-preview-${profile.id}`, String(profile.id))
  }

  useEffect(() => () => {
    stopReadAloud()
    const context = speechAudioContextRef.current
    speechAudioContextRef.current = null
    if (context && context.state !== 'closed') void context.close().catch(() => {})
  }, [])

  const getInitials = (name) => {
    const words = name.trim().split(/\s+/).filter(Boolean)
    if (!words.length) return 'O'
    return words.slice(0, 2).map(word => word[0].toUpperCase()).join('')
  }

  const getChatInitials = (title) => {
    const words = String(title || 'Chat').trim().split(/\s+/).filter(Boolean)
    if (!words.length) return 'C'
    if (words.length === 1) return words[0].slice(0, 3).toUpperCase()
    return words.slice(0, 3).map(word => word[0].toUpperCase()).join('')
  }

  const getFirstName = (name) => {
    return name.trim().split(/\s+/).filter(Boolean)[0] || ''
  }

  const updateUserName = (name) => {
    setNameDraft(name)
    setUserName(name)
    localStorage.setItem('nova-user-name', name)
  }

  const resizeSidebar = (event) => {
    event.preventDefault()

    const startX = event.clientX
    const startWidth = sidebarCollapsed ? 72 : sidebarWidth

    const handleMove = (moveEvent) => {
      // The resize handle is now the only way to collapse/expand the sidebar.
      // Drag all the way down to 72px to enter compact mode.
      const rawWidth = startWidth + (moveEvent.clientX - startX)
      const nextWidth = Math.min(280, Math.max(72, rawWidth))

      if (nextWidth <= 90) {
        setSidebarCollapsed(true)
        setSidebarWidth(72)
      } else {
        setSidebarCollapsed(false)
        setSidebarWidth(nextWidth)
      }
    }

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  const loadChats = useCallback(async (selectLatest = false) => {
    const requestRevision = chatRevisionRef.current
    try {
      const response = await fetch('http://127.0.0.1:8000/api/chats')

      if (!response.ok) {
        throw new Error('Could not load chat history')
      }

      const data = await response.json()
      const nextChats = Array.isArray(data.chats) ? data.chats : []

      // Do not let an older history response overwrite a chat created or
      // updated while this request was in flight.
      if (requestRevision !== chatRevisionRef.current) return

      setChats(nextChats)

      // On first load, open the newest saved conversation.
      // Otherwise keep whichever conversation the user is currently viewing.
      if (selectLatest && nextChats.length) {
        setActiveChatId((currentChatId) => currentChatId ?? nextChats[0].id)
      }
    } catch (error) {
      console.error('Chat history:', error)
    }
  }, [])

  const createNewChat = (event) => {
    if (event) event.preventDefault()
    if (running || taskStarting) return

    // A new chat starts from Home, where the user can enter the first prompt.
    // The backend conversation is created only when that prompt is submitted.
    setActiveChatId(null)
    setActiveSection('home')
    setTask('')
    setStatusMessage('')
    setActivityMessage('Ready for your next request.')
  }

  const openChat = (chatId) => {
    setActiveChatId(chatId)
    setActiveSection('chat')
    setActivityMessage('Conversation ready. Send a message to continue.')
  }

  const activeChat = chats.find((chat) => chat.id === activeChatId) || null
  const activeChatMessages = activeChat?.messages || []
  const latestAssistantMessageIndex = activeChatMessages.reduce((last, message, index) => (
    message?.role === 'user' ? last : index
  ), -1)
  const normalizedChatSearch = chatSearchQuery.trim().toLowerCase()
  const visibleChats = normalizedChatSearch
    ? chats.filter((chat) => {
        const messageText = (Array.isArray(chat.messages) ? chat.messages : [])
          .map((message) => message?.content || message?.text || '')
          .join(' ')
        return `${chat.title || ''} ${messageText}`.toLowerCase().includes(normalizedChatSearch)
      })
    : chats

  useEffect(() => {
    const container = conversationMessagesRef.current
    if (!container) return
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
  }, [activeChatId, activeChat?.messages?.length])

  const deleteChat = async (chatId) => {
    const chatToDelete = chats.find((chat) => String(chat.id) === String(chatId))
    const title = chatToDelete?.title || 'this conversation'
    const confirmed = window.confirm(
      `Permanently delete "${title}"?\n\nThis removes the conversation from NOVA's saved chat history and cannot be undone.`
    )
    if (!confirmed) return

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chats/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId }),
      })

      if (!response.ok) {
        throw new Error('Could not delete chat')
      }

      // Remove only the exact conversation the user selected. Do not replace
      // the whole local history with a possibly incomplete response payload.
      await response.json().catch(() => ({}))

      chatRevisionRef.current += 1
      setChats((current) => current.filter((chat) => String(chat.id) !== String(chatId)))

      if (String(activeChatId) === String(chatId)) {
        setActiveChatId(null)
      }
    } catch (error) {
      console.error('Delete chat:', error)
      setStatusMessage('Could not delete chat.')
    }
  }

  const savePromptToHistory = async (command, forceNewChat = false) => {
    try {
      // Homepage submissions always create a new conversation, regardless of
      // any previously selected chat ID left over from initial history loading.
      if (forceNewChat || !activeChatId) {
        const response = await fetch('http://127.0.0.1:8000/api/chats', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command }),
        })

        if (!response.ok) {
          throw new Error('Could not create chat')
        }

        const data = await response.json()
        const createdChat = data.chat

        chatRevisionRef.current += 1
        setChats((current) => [
          createdChat,
          ...current.filter((chat) => chat.id !== createdChat.id),
        ])

        setActiveChatId(createdChat.id)

        return {
          chatId: createdChat.id,
          createdNewChat: true,
        }
      }

      // Active chat = continue the existing conversation.
      const response = await fetch(
        'http://127.0.0.1:8000/api/chats/append',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: activeChatId,
            command,
          }),
        }
      )

      if (!response.ok) {
        throw new Error('Could not save message')
      }

      const data = await response.json()

      chatRevisionRef.current += 1
      setChats((current) =>
        current.map((chat) =>
          chat.id === activeChatId ? data.chat : chat
        )
      )

      return {
        chatId: activeChatId,
        createdNewChat: false,
      }
    } catch (error) {
      console.error('Chat history save:', error)
      return null
    }
  }

  const pushVoiceLevel = (value) => {
    const numeric = Number(value)
    const next = Number.isFinite(numeric) ? Math.max(0, Math.min(1, numeric)) : 0
    setVoiceLevels((current) => [...current.slice(1), next])
  }

  const resetVoiceLevels = () => setVoiceLevels(Array(28).fill(0.015))

  const stopVoiceLevelMonitor = async () => {
    const meter = voiceLevelMonitorRef.current
    voiceLevelMonitorRef.current = null
    if (meter) {
      try { await meter.stop() } catch (error) {
        console.warn('NOVA could not stop the microphone visualizer:', error)
      }
    }
    resetVoiceLevels()
  }

  const updateTaskDraft = (value) => {
    setTask(value)
    if (voiceTranscriptReady) {
      setVoiceTranscriptReady(false)
      setVoiceNotice('')
    }
  }

  const runTask = async (commandOverride = null, sourceOptions = {}) => {
    const command = (commandOverride ?? task).trim()
    if (!command || running || taskStarting || taskSubmissionRef.current) return
    const submittedFromVoice = voiceTranscriptReady || Boolean(sourceOptions.fromVoiceMode)
    // Voice Mode streams model text into Voicebox as it arrives. The mic mute
    // remains input-only: it must not cancel NOVA's speaker output.
    const speakThisVoiceReply = Boolean(sourceOptions.fromVoiceMode || (submittedFromVoice && speakVoiceCommandReplies))
    const voiceStreamingEnabled = Boolean(sourceOptions.fromVoiceMode && speakThisVoiceReply)

    if (sourceOptions.fromVoiceMode) {
      // handleContinuousVoiceUtterance marks the previous session cancelled
      // before submitting a new turn. Re-arm the new turn even when TTS is
      // delivered after the final reply rather than streamed token-by-token.
      voiceStreamSessionCancelledRef.current = false
      voiceModeStreamedTextRef.current = ''
      setVoiceModeAssistantTranscript('')
    }

    taskSubmissionRef.current = true
    if (sourceOptions.fromVoiceMode) {
      setVoiceModeTurns((current) => [...current, { role: 'you', content: command, id: `you-${Date.now()}` }])
    }
    setTypewriterTarget(null)
    if (voiceModeOpen) { setVoiceRoomStatus('thinking'); setVoiceModeCaptionError('') }
    if (speakThisVoiceReply) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      if (AudioContextClass) {
        try {
          if (!speechAudioContextRef.current || speechAudioContextRef.current.state === 'closed') {
            speechAudioContextRef.current = new AudioContextClass()
          }
          if (speechAudioContextRef.current.state === 'suspended') void speechAudioContextRef.current.resume().catch(() => {})
        } catch (audioUnlockError) {
          console.debug('NOVA could not pre-unlock audio for the voice reply:', audioUnlockError)
        }
      }
    }
    if (voiceStreamingEnabled) {
      // Create/start the empty TTS queue before sending the task. Otherwise the
      // first assistant_delta events can arrive before a queue exists.
      const voiceStreamKey = `voice-stream-${Date.now()}`
      const voiceStreamLanguage = conversationLanguage === 'auto'
        ? detectConversationLanguage(command, 'auto')
        : conversationLanguage
      void readAloudResponse('', voiceStreamKey, selectedVoiceProfileId, true, voiceStreamLanguage)
    }
    setTaskStarting(true)
    setTask('')
    setVoiceNotice('')
    setVoiceTranscriptReady(false)
    resetVoiceLevels()
    setStopArmed(false)
    setStatusMessage('')
    setActivityMessage('Preparing your conversation…')
    setActivityAgent('')

    // Every submission from Home starts a fresh conversation. A message sent
    // from an already-open conversation continues that conversation instead.
    const startedFromHome = activeSection === 'home'
    const mustCreateNewChat = startedFromHome || !activeChatId
    if (startedFromHome) {
      setActiveChatId(null)
      setActiveSection('chat')
    }

    try {
      const saved = await savePromptToHistory(command, mustCreateNewChat)
      if (!saved?.chatId) {
        throw new Error('Could not save chat history. Please try sending your message again.')
      }
      if (saved.createdNewChat) setActiveSection('chat')

      setActivityMessage('Sending your request…')

      // Establish an event cursor before submitting the task so only events
      // produced by this request appear in its live activity feed.
      try {
        const baselineResponse = await fetch('http://127.0.0.1:8000/api/events')
        if (baselineResponse.ok) {
          const baselineData = await baselineResponse.json()
          const baselineEvents = Array.isArray(baselineData.events) ? baselineData.events : []
          const latestId = baselineEvents.reduce((latest, event) => (
            compareEventIds(event?.id, latest) > 0 ? String(event.id) : latest
          ), activityEventCursorRef.current)
          activityEventCursorRef.current = latestId
        }
      } catch (error) {
        console.debug('NOVA could not read the initial activity cursor:', error)
      }

      const response = await fetch('http://127.0.0.1:8000/api/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command,
          chat_id: saved.chatId,
          voice_stream: voiceStreamingEnabled,
          language: conversationLanguage,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Could not start the task')
      if (!data.task_id) throw new Error('NOVA backend did not return a task ID. Update api.py and restart NOVA.')
      activeTaskIdRef.current = String(data.task_id)

      setRunning(true)
      setTaskStarting(false)
      setBackendOnline(true)
      setActivityMessage('Planning your request…')

      // Poll the task result and the event feed together. Events are emitted by
      // the Router, Planner, Orchestrator and specialist agents as work happens.
      let finishedTask = null
      while (!finishedTask) {
        const [resultResponse, eventsResponse] = await Promise.all([
          fetch(`http://127.0.0.1:8000/api/task-result?task_id=${encodeURIComponent(data.task_id)}`),
          fetch(`http://127.0.0.1:8000/api/events?task_id=${encodeURIComponent(data.task_id)}&after=${encodeURIComponent(activityEventCursorRef.current)}`).catch((error) => {
            console.debug('NOVA activity feed temporarily unavailable:', error)
            return null
          }),
        ])

        if (eventsResponse?.ok) {
          const eventsData = await eventsResponse.json()
          const allEvents = Array.isArray(eventsData.events) ? eventsData.events : []
          const freshEvents = allEvents
          if (freshEvents.length) {
            activityEventCursorRef.current = String(freshEvents[freshEvents.length - 1].id)
            if (voiceStreamingEnabled) {
              const tokenEvents = freshEvents.filter((event) => (
                event?.event === 'assistant_token' && event?.kind === 'assistant_delta'
              ))
              for (const tokenEvent of tokenEvents) {
                const delta = String(tokenEvent?.message || '')
                if (!delta) continue
                voiceModeStreamedTextRef.current += delta
                setVoiceModeAssistantTranscript((current) => current + delta)
                voicePlaybackQueueRef.current?.appendText?.(delta)
              }
            }
            const activityEvents = freshEvents.filter((event) => event?.event !== 'assistant_token')
            const descriptions = activityEvents.map(describeActivityEvent).filter(Boolean)
            if (descriptions.length) setActivityMessage(descriptions[descriptions.length - 1])
            const latestAgent = [...activityEvents].reverse().find((event) => event?.agent)?.agent
            if (latestAgent) {
              const labels = { planner: 'Planner', research: 'Research agent', researcher: 'Research agent', browser: 'Browser agent', coding: 'Coding agent', file: 'File agent' }
              const key = String(latestAgent).toLowerCase().replace(/\s+agent$/i, '')
              setActivityAgent(labels[key] || `${String(latestAgent).replace(/[-_]/g, ' ')} agent`)
            }
          }
        }

        const resultData = await resultResponse.json()
        if (!resultResponse.ok) throw new Error(resultData.error || 'Could not retrieve NOVA response')

        const current = resultData.task
        if (current?.status === 'awaiting_approval' && current.approval) {
          setPendingApproval(current.approval)
          setStatusMessage('NOVA is waiting for your approval before taking this action.')
          setActivityMessage('Waiting for your approval before continuing…')
        } else {
          setPendingApproval(null)
        }
        if (current && ['completed', 'failed', 'partial', 'stopped', 'timed_out'].includes(current.status)) {
          finishedTask = current
          break
        }
        await new Promise((resolve) => window.setTimeout(resolve, voiceStreamingEnabled ? 100 : 700))
      }

      if (voiceStreamingEnabled && data?.task_id) {
        try {
          const finalEventsResponse = await fetch(
            `http://127.0.0.1:8000/api/events?task_id=${encodeURIComponent(data.task_id)}&after=${encodeURIComponent(activityEventCursorRef.current)}`
          )
          if (finalEventsResponse.ok) {
            const finalEventsData = await finalEventsResponse.json()
            const finalEvents = Array.isArray(finalEventsData.events) ? finalEventsData.events : []
            if (finalEvents.length) {
              activityEventCursorRef.current = String(finalEvents[finalEvents.length - 1].id)
              for (const tokenEvent of finalEvents) {
                if (tokenEvent?.event !== 'assistant_token' || tokenEvent?.kind !== 'assistant_delta') continue
                const delta = String(tokenEvent?.message || '')
                if (!delta) continue
                voiceModeStreamedTextRef.current += delta
                setVoiceModeAssistantTranscript((current) => current + delta)
                voicePlaybackQueueRef.current?.appendText?.(delta)
              }
            }
          }
        } catch (error) {
          console.debug('NOVA final voice-token event drain was unavailable:', error)
        }
      }

      await loadChats(false)
      if (finishedTask?.reply) {
        const finalReplyText = String(finishedTask.reply)
        setTypewriterTarget({ chatId: saved.chatId, content: finalReplyText, nonce: Date.now() })
        if (sourceOptions.fromVoiceMode) {
          setVoiceModeTurns((current) => [...current, { role: 'nova', content: finalReplyText, id: `nova-${Date.now()}` }])
          // Move the live streaming preview into the committed chat message so
          // the final reply is shown once, not duplicated as a second bubble.
          setVoiceModeAssistantTranscript('')
        }
        if (speakThisVoiceReply && finishedTask.status === 'completed') {
          if (voiceStreamingEnabled && voiceStreamSessionCancelledRef.current) {
            stopReadAloud()
          } else if (voiceStreamingEnabled && voiceModeStreamedTextRef.current.trim()) {
            voicePlaybackQueueRef.current?.finishInput?.()
          } else {
            // Browser/Research/Reaction replies do not necessarily originate
            // from the Chat token stream. Speak their final result only after
            // the existing Orchestrator reports task completion.
            if (voiceStreamingEnabled) stopReadAloud()
            if (!voiceStreamSessionCancelledRef.current) {
              window.setTimeout(() => {
                void readAloudResponse(finalReplyText, `voice-command-${data.task_id}`)
              }, 0)
            }
          }
        } else {
          if (voiceStreamingEnabled) stopReadAloud()
          if (voiceModeOpen) setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'listening' : 'muted')
        }
      } else if (voiceStreamingEnabled) {
        stopReadAloud()
      }
      setRunning(false)
      setStopArmed(false)
      setPendingApproval(null)
      if (!finishedTask.reply) {
        setStatusMessage('The task finished, but NOVA did not return a reply.')
        if (sourceOptions.fromVoiceMode) setVoiceModeCaptionError('The task finished, but NOVA did not return a reply.')
        setActivityMessage('The task finished, but no reply was returned.')
      } else if (finishedTask.status === 'completed') {
        const agentName = String(finishedTask.agent || 'NOVA').replace(/^./, (letter) => letter.toUpperCase())
        setStatusMessage('')
        setActivityMessage(`${agentName} Agent completed your request. Your response is ready.`)
      } else {
        const message = `NOVA finished with status: ${finishedTask.status}.`
        setStatusMessage(message)
        if (sourceOptions.fromVoiceMode) setVoiceModeCaptionError(message)
        setActivityMessage(`Task finished with status: ${finishedTask.status}.`)
      }
    } catch (error) {
      if (voiceStreamingEnabled) stopReadAloud()
      console.error('NOVA task:', error)
      setRunning(false)
      setStopArmed(false)
      setPendingApproval(null)
      const message = error instanceof Error ? error.message : 'NOVA could not complete the request.'
      setStatusMessage(message)
      if (sourceOptions.fromVoiceMode) setVoiceModeCaptionError(message)
      setActivityMessage(`NOVA couldn't complete the request. ${message}`)
      // Refresh in case the backend saved a final error response before the
      // connection was interrupted.
      await loadChats(false)
    } finally {
      activeTaskIdRef.current = null
      setTaskStarting(false)
      taskSubmissionRef.current = false
      if (sourceOptions.fromVoiceMode && voiceModeOpenRef.current) {
        const queue = voicePlaybackQueueRef.current
        if (!queue?.hasPendingAudio?.()) {
          setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'ready' : 'muted')
        }
      }
    }
  }


  // Keep the latest task handler available to the long-lived microphone
  // callbacks without restarting the capture graph on every React render.
  runTaskRef.current = runTask

  const waitForCurrentVoiceTaskToStop = async () => {
    const startedAt = Date.now()
    let stopRequested = false
    while (taskSubmissionRef.current && voiceModeOpenRef.current && Date.now() - startedAt < 18000) {
      const taskId = activeTaskIdRef.current
      if (taskId && !stopRequested) {
        stopRequested = true
        const response = await fetch('http://127.0.0.1:8000/api/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_id: taskId }),
        })
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}))
          // The task can finish between the last UI poll and this stop request.
          // Treat that race as safe only when the task-result endpoint confirms
          // that the old request is already terminal.
          const resultResponse = await fetch(`http://127.0.0.1:8000/api/task-result?task_id=${encodeURIComponent(taskId)}`).catch(() => null)
          const resultPayload = resultResponse?.ok ? await resultResponse.json().catch(() => ({})) : {}
          const status = resultPayload?.task?.status
          if (!['completed', 'failed', 'partial', 'stopped', 'timed_out'].includes(status)) {
            throw new Error(payload.error || 'NOVA could not stop the previous voice task.')
          }
        }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 100))
    }
    if (taskSubmissionRef.current) {
      throw new Error('NOVA is still finishing the previous request. Try speaking again in a moment.')
    }
    // Let React commit the completed-task state before submitting the next turn.
    await new Promise((resolve) => window.setTimeout(resolve, 60))
  }

  const handleContinuousVoiceInput = async (input) => {
    if (!voiceModeOpenRef.current || !voiceModeMicEnabledRef.current) return
    const entry = typeof input === 'string' ? { transcript: input } : input
    if (voiceAutoSubmitLockRef.current) {
      // Preserve both browser-recognised text and Voicebox WAV fallbacks while
      // a previous turn is being submitted or interrupted.
      if (voicePendingUtterancesRef.current.length < 4) voicePendingUtterancesRef.current.push(entry)
      return
    }
    voiceAutoSubmitLockRef.current = true
    const queueAtStart = voicePlaybackQueueRef.current
    const wasPaused = Boolean(queueAtStart?.isPaused?.())
    setVoiceRoomStatus('thinking')
    setVoiceModeCaptionError('')
    setVoiceModeTranscript('')

    try {
      const rawTranscript = entry?.transcript || await transcribeVoiceSegment(entry?.wavBlob, { language: conversationLanguage })
      const command = normalizeNOVAAssistantNameTranscript(rawTranscript).trim()
      if (!voiceModeOpenRef.current) return
      if (!command) throw new Error('No clear speech was recognised.')
      if (!voiceContinuousEnabledRef.current) {
        // Manual conversation mode keeps the transcript for review instead of
        // submitting automatically. If VAD paused playback, restore it now.
        setVoiceCaptionsEnabled(true)
        setVoiceModeTranscript(command)
        if (queueAtStart?.isPaused?.()) queueAtStart.resume()
        setVoiceRoomStatus(queueAtStart?.isPlaying?.() ? 'speaking' : (voiceModeMicEnabledRef.current ? 'ready' : 'muted'))
        return
      }
      if (/^(?:uh+|um+|erm+|hmm+|mm+)[.!?\s]*$/i.test(command)) {
        if (queueAtStart?.isPaused?.()) queueAtStart.resume()
        setVoiceRoomStatus(queueAtStart?.isPlaying?.() ? 'speaking' : 'ready')
        return
      }

      const isResumeCommand = /^(?:please\s+)?(?:continue|go on|carry on|keep going|resume)(?:\s+please)?[.!?\s]*$/i.test(command)
      if (isResumeCommand && queueAtStart?.isPaused?.()) {
        setVoiceModeTurns((current) => [...current, { role: 'you', content: command, id: `you-${Date.now()}` }])
        setVoiceModeTranscript('')
        voiceInterruptionPendingRef.current = false
        queueAtStart.resume()
        setVoiceRoomStatus(queueAtStart.isPlaying() ? 'speaking' : 'thinking')
        return
      }

      // A confirmed utterance is a real new turn. Only now cancel the old
      // response; a cough/noise or failed transcription simply resumes it.
      voiceStreamSessionCancelledRef.current = true
      if (taskSubmissionRef.current) await waitForCurrentVoiceTaskToStop()
      if (!voiceModeOpenRef.current) return
      stopReadAloud()
      voiceInterruptionPendingRef.current = false

      setVoiceModeTranscript('')
      setVoiceRoomStatus('thinking')
      const submitTask = runTaskRef.current
      if (typeof submitTask !== 'function') throw new Error('NOVA voice task handler is not ready.')
      const taskPromise = submitTask(command, { fromVoiceMode: true })
      if (taskPromise && typeof taskPromise.catch === 'function') {
        void taskPromise.catch((error) => console.error('NOVA automatic voice task:', error))
      }
    } catch (error) {
      console.warn('NOVA voice turn:', error)
      if (voiceModeOpenRef.current && taskSubmissionRef.current) {
        // The old task is still live, so preserve its right to finish when
        // stopping it was unsuccessful. The paused queue is resumed below.
        voiceStreamSessionCancelledRef.current = false
      }
      setVoiceModeCaptionError(error instanceof Error ? error.message : 'NOVA could not understand that utterance.')
      setVoiceModeTranscript('')
      if (wasPaused || voicePlaybackQueueRef.current?.isPaused?.()) {
        voicePlaybackQueueRef.current?.resume?.()
      }
      if (voiceModeMicEnabledRef.current) {
        const activeQueue = voicePlaybackQueueRef.current
        setVoiceRoomStatus(activeQueue?.isPlaying?.() ? 'speaking' : 'ready')
      }
    } finally {
      voiceAutoSubmitLockRef.current = false
      const nextUtterance = voicePendingUtterancesRef.current.shift()
      if (nextUtterance && voiceModeOpenRef.current) {
        window.setTimeout(() => { void handleContinuousVoiceInput(nextUtterance) }, 0)
      }
    }
  }

  const handleContinuousVoiceUtterance = (wavBlob) => handleContinuousVoiceInput({ wavBlob })
  const handleContinuousBrowserTranscript = (transcript) => handleContinuousVoiceInput({ transcript })

  const respondToApproval = async (decision) => {
    const approval = pendingApproval
    if (!approval || approvalBusy) return
    setApprovalBusy(true)
    try {
      const response = await fetch('http://127.0.0.1:8000/api/approval/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approval_id: approval.approval_id,
          task_id: approval.task_id,
          decision,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Could not submit your approval decision.')
      setStatusMessage(decision === 'approve'
        ? 'Approved. NOVA is continuing the task.'
        : 'Declined. NOVA will not perform that action.')
    } catch (error) {
      console.error('NOVA approval:', error)
      setStatusMessage(error instanceof Error ? error.message : 'Could not submit approval.')
    } finally {
      setApprovalBusy(false)
    }
  }

  // Shared voice handler for Home and Chat. Auto tries browser on-device speech
  // recognition first, then the browser's regular speech service, then Voicebox.
  // Voicebox-only and Online Recognition remain selectable in Settings.
  // Transcripts are always placed in the composer; they are never auto-sent.
  const discardVoiceBackup = async () => {
    const backup = voiceBackupRef.current
    voiceBackupRef.current = null
    voiceRetryAudioRef.current = null
    if (backup) {
      try { await backup.abort() } catch (error) {
        console.warn('NOVA could not discard the temporary voice recording:', error)
      }
    }
    await stopVoiceLevelMonitor()
  }

  const transcribeSavedVoiceAudio = async () => {
    if (localTranscribing) return

    setLocalTranscribing(true)
    setLocalRetryAvailable(false)
    setVoiceNotice('')
    setVoiceTranscriptReady(false)

    const recognition = recognitionRef.current
    recognitionRef.current = null
    voiceRecognitionFailedRef.current = true
    try { recognition?.abort?.() } catch (error) {
      console.debug('NOVA could not abort the previous speech session:', error)
    }
    setListening(false)

    try {
      let audio = voiceRetryAudioRef.current
      if (!audio) {
        const backup = voiceBackupRef.current
        if (!backup) {
          throw new Error('The local audio recording is no longer available. Please record your command again.')
        }
        try {
          audio = await backup.stop()
        } catch (error) {
          voiceBackupRef.current = null
          try { await backup.abort() } catch (abortError) {
            console.debug('NOVA could not discard the temporary voice recording:', abortError)
          }
          throw error
        }
        voiceBackupRef.current = null
        voiceRetryAudioRef.current = audio
      }

      setVoiceNotice('')
      const result = await transcribeWithVoicebox(audio, conversationLanguage)
      const transcript = normalizeNOVAAssistantNameTranscript(result.text).trim()
      if (!transcript) throw new Error('Voicebox did not detect any speech. Please try again.')

      setTask(transcript)
      voiceRetryAudioRef.current = null
      voiceRecognitionFailedRef.current = false
      setLocalRetryAvailable(false)
      setVoiceNotice('Voice text ready · Review and send')
      setVoiceTranscriptReady(true)
      setVoiceLiveTranscript('')
    } catch (error) {
      console.error('NOVA local voice transcription:', error)
      setLocalRetryAvailable(Boolean(voiceRetryAudioRef.current || voiceBackupRef.current))
      setVoiceNotice(error instanceof Error ? error.message : 'Voice transcription failed. Try again.')
    } finally {
      updateActiveVoiceInputMode(null)
      autoFallbackStartedRef.current = false
      setLocalTranscribing(false)
      resetVoiceLevels()
    }
  }

  const retryVoiceLocally = () => transcribeSavedVoiceAudio()

  const startLocalVoiceInput = async () => {
    await discardVoiceBackup()
    setLocalRetryAvailable(false)
    voiceRecognitionFailedRef.current = false
    autoFallbackStartedRef.current = false

    try {
      voiceBackupRef.current = await startWavBackup({ onLevel: pushVoiceLevel })
      updateActiveVoiceInputMode('local')
      setVoiceNotice('')
      setVoiceTranscriptReady(false)
      setVoiceLiveTranscript('')
      setListening(true)
    } catch (error) {
      console.error('NOVA local microphone capture:', error)
      updateActiveVoiceInputMode(null)
      setListening(false)
      setVoiceNotice(error instanceof Error ? error.message : 'Could not start on-device voice input. Check microphone permissions and try again.')
    }
  }

  const toggleVoiceInput = async () => {
    if (localTranscribing) return

    if (listening) {
      if (activeVoiceInputModeRef.current === 'local') {
        await transcribeSavedVoiceAudio()
      } else {
        try { recognitionRef.current?.stop() } catch (error) {
          console.warn('NOVA could not stop browser speech recognition:', error)
        }
      }
      return
    }

    if (running) {
      setVoiceNotice('Stop the current task before starting voice input.')
      return
    }

    await discardVoiceBackup()
    setLocalRetryAvailable(false)
    voiceRecognitionFailedRef.current = false
    autoFallbackStartedRef.current = false
    setVoiceNotice('')
    setVoiceTranscriptReady(false)
    setVoiceLiveTranscript('')
    resetVoiceLevels()

    const SpeechRecognition = getBrowserSpeechRecognitionConstructor(window)
    const selectedMode = voiceRecognitionMode

    // Auto prefers the browser's on-device engine, then tries its standard
    // recognizer (which may be network-backed), and finally falls back to Voicebox.
    if (selectedMode === 'local') {
      await startLocalVoiceInput()
      return
    }

    if (!SpeechRecognition) {
      setVoiceNotice('Browser speech recognition is unavailable · switching to Voicebox')
      await startLocalVoiceInput()
      return
    }

    let recognitionLocale = getBrowserRecognitionLocale(conversationLanguage, navigator.language || 'en-IN')
    let useBrowserOnDevice = false

    if (selectedMode === 'auto') {
      const localeCandidates = getBrowserOnDeviceRecognitionLocales(
        recognitionLocale,
        navigator.language || 'en-IN',
      )
      setVoiceNotice('Checking this browser’s on-device speech recognition…')
      const readiness = await ensureBrowserOnDeviceRecognition(SpeechRecognition, localeCandidates)
      if (readiness.available) {
        recognitionLocale = readiness.locale
        useBrowserOnDevice = true
        if (readiness.installedNow) setVoiceNotice(`${recognitionLocale} local speech model installed · starting microphone…`)
        console.info('[NOVA STT] Compact mic provider: browser on-device', recognitionLocale)
      } else {
        console.info('[NOVA STT] Browser-local STT unavailable; trying the browser native recognizer before Voicebox:', readiness.reason || readiness.message)
        setVoiceNotice('On-device speech recognition unavailable · trying browser speech recognition…')
      }
    }

    try {
      const recognition = new SpeechRecognition()
      recognitionRef.current = recognition
      updateActiveVoiceInputMode(useBrowserOnDevice ? 'browser-local' : 'online')
      let liveTranscript = ''
      recognition.processLocally = useBrowserOnDevice
      recognition.lang = recognitionLocale
      recognition.continuous = true
      recognition.interimResults = true
      recognition.maxAlternatives = 1

      let levelMeterRequested = false
      const startOnlineLevelMeter = () => {
        if (levelMeterRequested || useBrowserOnDevice) return
        levelMeterRequested = true
        void startMicLevelMonitor(pushVoiceLevel).then((meter) => {
          if (recognitionRef.current === recognition) {
            voiceLevelMonitorRef.current = meter
          } else {
            void meter.stop()
          }
        }).catch((meterError) => {
          console.info('NOVA audio-level visualizer unavailable; speech recognition will continue:', meterError)
        })
      }

      recognition.onstart = () => {
        setListening(true)
        setVoiceNotice(useBrowserOnDevice
          ? `Listening · browser on-device recognition (${recognitionLocale})`
          : 'Listening · browser speech recognition')
        if (!useBrowserOnDevice) startOnlineLevelMeter()
      }

      recognition.onresult = (event) => {
        let interimTranscript = ''
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index]
          const words = result?.[0]?.transcript || ''
          if (result.isFinal) liveTranscript = `${liveTranscript} ${words}`.trim()
          else interimTranscript += ` ${words}`
        }

        const currentTranscript = normalizeNOVAAssistantNameTranscript(`${liveTranscript} ${interimTranscript}`).trim()
        if (currentTranscript) {
          setTask(currentTranscript)
          setVoiceLiveTranscript(currentTranscript)
        }
      }

      recognition.onerror = (event) => {
        setListening(false)
        if (event.error === 'aborted' || event.error === 'no-speech') return
        voiceRecognitionFailedRef.current = true
        const messages = {
          'not-allowed': 'Microphone access was blocked by the browser.',
          'service-not-allowed': 'The browser speech-recognition service is blocked.',
          'no-speech': 'The browser did not detect speech.',
          network: 'The browser recognition service reported a network error.',
          'audio-capture': 'The browser could not access the microphone.',
          'language-not-supported': 'The browser does not have the selected local speech model.',
        }
        const message = messages[event.error] ?? `Browser recognition failed: ${event.error}.`
        setVoiceNotice(`${message} Voicebox will handle speech recognition if no transcript arrives.`)
      }

      recognition.onend = async () => {
        setListening(false)
        if (recognitionRef.current === recognition) recognitionRef.current = null
        void stopVoiceLevelMonitor()

        if ((selectedMode === 'auto' || selectedMode === 'online') && !liveTranscript.trim() && !autoFallbackStartedRef.current) {
          autoFallbackStartedRef.current = true
          await startLocalVoiceInput()
          if (activeVoiceInputModeRef.current === 'local') {
            setVoiceNotice(voiceRecognitionFailedRef.current
              ? 'Browser recognition failed · Voicebox is now handling speech recognition'
              : 'Browser returned no transcript · Voicebox is now handling speech recognition')
          }
          return
        }

        if (liveTranscript.trim()) {
          updateActiveVoiceInputMode(null)
          setVoiceNotice('Voice text ready · Review and send')
          setVoiceTranscriptReady(true)
          setVoiceLiveTranscript('')
          return
        }

        updateActiveVoiceInputMode(null)
        setVoiceNotice('No speech was transcribed · Try again or use Voicebox mode')
      }

      recognition.start()
    } catch (error) {
      recognitionRef.current = null
      setListening(false)
      updateActiveVoiceInputMode(null)
      console.error('NOVA browser speech recognition:', error)
      if ((selectedMode === 'auto' || selectedMode === 'online') && !autoFallbackStartedRef.current) {
        autoFallbackStartedRef.current = true
        setVoiceNotice('Browser speech recognition could not start · switching to Voicebox')
        await startLocalVoiceInput()
      } else {
        setVoiceNotice(error instanceof Error ? error.message : 'Could not start browser speech recognition. Check microphone permissions.')
        void stopVoiceLevelMonitor()
      }
    }
  }

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort?.()
      const backup = voiceBackupRef.current
      voiceBackupRef.current = null
      const meter = voiceLevelMonitorRef.current
      voiceLevelMonitorRef.current = null
      try { meter?.stop?.() } catch (error) {
        console.debug('NOVA could not stop the microphone level monitor:', error)
      }
      if (backup) void backup.abort()
      voiceRetryAudioRef.current = null
    }
  }, [])

  const openVoiceMode = () => {
    voiceModeOpenRef.current = true
    // Browsers may block audio started only after the asynchronous STT/model
    // request. Create and resume the shared context now, in the user's click
    // gesture, then reuse it for every Voicebox TTS chunk in this session.
    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    if (AudioContextClass) {
      try {
        let context = speechAudioContextRef.current
        if (!context || context.state === 'closed') {
          context = new AudioContextClass()
          speechAudioContextRef.current = context
        }
        if (context.state === 'suspended') {
          void context.resume().catch((error) => {
            console.warn('NOVA could not unlock voice playback:', error)
            setSpeechError('Browser audio is blocked. Click the Voice Mode window once, then try again.')
          })
        }
      } catch (error) {
        console.warn('NOVA could not prepare voice playback:', error)
        setSpeechError(error instanceof Error ? error.message : 'Could not prepare browser audio playback.')
      }
    }
    voiceOrbLevelRef.current = -1
    setVoiceModeMicEnabled(true)
    setVoiceModeTranscript('')
    setVoiceModeAssistantTranscript('')
    setVoiceModeTurns([])
    voiceAutoSubmitLockRef.current = false
    voicePendingUtterancesRef.current = []
    voiceInterruptionPendingRef.current = false
    setVoiceModeCaptionError('')
    setVoiceRoomStatus('requesting')
    setVoiceModeOpen(true)
  }

  const retryVoiceCapture = () => {
    setVoiceModeCaptionError('')
    setVoiceRoomStatus('requesting')
    setVoiceCaptureRetryNonce((value) => value + 1)
  }

  const closeVoiceMode = () => {
    voiceModeOpenRef.current = false
    voicePendingUtterancesRef.current = []
    voiceOrbLevelRef.current = -1
    voiceStreamSessionCancelledRef.current = true
    voiceInterruptionPendingRef.current = false
    voiceActivityCaptureRef.current?.stop?.()
    voiceActivityCaptureRef.current = null
    try { voiceModeRecognitionRef.current?.abort?.() } catch (error) { console.debug('NOVA could not stop browser recognition:', error) }
    voiceModeRecognitionRef.current = null
    voiceModeRecognitionStartRef.current = null
    voiceModeBrowserRecognitionActiveRef.current = false
    voiceModeBrowserFinalTranscriptRef.current = ''
    voiceModeBrowserInterimTranscriptRef.current = ''
    stopReadAloud()
    setVoiceModeOpen(false)
    setVoiceRoomStatus('idle')
    setVoiceModeAssistantTranscript('')
    setVoiceModeTurns([])
  }

  const submitVoiceModeTranscript = () => {
    const command = String(voiceModeTranscript || '').trim()
    if (!command || running || taskStarting) return
    setVoiceModeCaptionError('')
    setVoiceModeTranscript('')
    setVoiceRoomStatus('thinking')
    void runTask(command, { fromVoiceMode: true })
  }



  const handleActionButton = async () => {
    // Same two-stage behavior as the old keyboard ESC control:
    // 1st press = stop the current task.
    // 2nd press = close the NOVA browser worker.
    if (running) {
      try {
        await fetch('http://127.0.0.1:8000/api/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_id: activeTaskIdRef.current }),
        })
        setStopArmed(true)
        setStatusMessage('Stopping… press again to close NOVA.')
        setActivityMessage('Stopping the current task…')
      } catch (error) {
        console.error(error)
        setStatusMessage('Could not stop the task.')
        setActivityMessage('NOVA could not stop the task. You can try again.')
      }
      return
    }

    if (stopArmed) {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/close', { method: 'POST' })
        if (!response.ok) throw new Error('Could not close NOVA')
        setRunning(false)
        setBackendOnline(true)
        setStopArmed(false)
        setStatusMessage('NOVA agent closed.')
        setActivityMessage('Browser session closed.')
      } catch (error) {
        console.error(error)
        setStatusMessage('Could not close NOVA.')
        setActivityMessage('NOVA could not close the browser worker.')
      }
      return
    }

    if (!task.trim()) {
      openVoiceMode()
      return
    }

    runTask()
  }

  useEffect(() => {
    // Defer the initial history request to the next task so the effect only
    // schedules external work; loadChats updates React state after the fetch.
    const initialLoadTimer = window.setTimeout(() => {
      void loadChats(true)
    }, 0)
    return () => window.clearTimeout(initialLoadTimer)
  }, [loadChats])

  useEffect(() => {
    if (!voiceModeOpen) return undefined

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleVoiceEscape = (event) => {
      if (event.key === 'Escape') closeVoiceMode()
    }
    window.addEventListener('keydown', handleVoiceEscape)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleVoiceEscape)
    }
  }, [voiceModeOpen])

  // Keep microphone mute state available to the audio analyser without
  // restarting the browser media stream every time the button is toggled.
  useEffect(() => {
    voiceModeMicEnabledRef.current = voiceModeMicEnabled
    const stream = voiceModeStreamRef.current
    stream?.getAudioTracks?.().forEach((track) => {
      track.enabled = voiceModeMicEnabled
    })
    voiceActivityCaptureRef.current?.setEnabled?.(voiceModeMicEnabled)

    if (!voiceModeMicEnabled) {
      // SpeechRecognition owns its own browser microphone capture in order to
      // use the standard API consistently across Edge, Chrome and Brave.
      // Stop that capture as well as the VAD track when the user mutes the mic.
      try { voiceModeRecognitionRef.current?.abort?.() } catch (error) {
        console.debug('NOVA could not mute browser recognition:', error)
      }
      voiceModeRecognitionRef.current = null
      voiceModeBrowserRecognitionActiveRef.current = false
      voiceModeBrowserFinalTranscriptRef.current = ''
      voiceModeBrowserInterimTranscriptRef.current = ''
      voiceOrbLevelRef.current = 0
      const playbackQueue = voicePlaybackQueueRef.current
      // Muting is strictly microphone input control. If speech was paused by
      // VAD just before the mute click, resume it; never cancel the TTS queue.
      if (playbackQueue?.isPaused?.()) playbackQueue.resume()
      voiceInterruptionPendingRef.current = false
      if (playbackQueue?.isPlaying?.()) setVoiceRoomStatus('speaking')
      else if (playbackQueue?.hasPendingAudio?.()) setVoiceRoomStatus('thinking')
      else setVoiceRoomStatus('muted')
    } else if (voiceModeOpen && stream) {
      voiceOrbLevelRef.current = 0
      setVoiceRoomStatus('ready')
    } else if (voiceModeOpen) {
      voiceOrbLevelRef.current = -1
      setVoiceRoomStatus((current) => (current === 'muted' ? 'unavailable' : current))
    }
    if (voiceModeMicEnabled && voiceModeOpen && !voiceModeRecognitionRef.current) {
      voiceModeRecognitionStartRef.current?.()
    }
  }, [voiceModeMicEnabled, voiceModeOpen])

  // Continuous Voice Mode prefers browser on-device STT in Auto mode across
  // Edge, Chrome, Brave, and any other browser exposing the standard local API.
  // If local browser recognition is absent, Voicebox transcribes the VAD WAV
  // segments. Voicebox remains the TTS engine in every mode. The Web Speech API
  // owns its microphone capture, so start() is used instead of the non-standard
  // MediaStreamTrack overload for broader browser compatibility.
  useEffect(() => {
    if (!voiceModeOpen) return undefined

    let disposed = false
    let capture = null
    let shouldRestartRecognition = true
    let restartTimer = null
    setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'requesting' : 'muted')
    setVoiceModeCaptionError('')
    voiceModeBrowserRecognitionActiveRef.current = false
    voiceModeBrowserFinalTranscriptRef.current = ''
    voiceModeBrowserInterimTranscriptRef.current = ''

    const startBrowserRecognition = async () => {
      const SpeechRecognition = getBrowserSpeechRecognitionConstructor(window)
      if (!SpeechRecognition) {
        setVoiceModeCaptionError('Browser speech recognition is unavailable. Voicebox will handle speech recognition.')
        return
      }

      let locale = getBrowserRecognitionLocale(conversationLanguage, navigator.language || 'en-IN')
      let useBrowserOnDevice = false
      if (voiceRecognitionMode === 'auto') {
        const localeCandidates = getBrowserOnDeviceRecognitionLocales(
          locale,
          navigator.language || 'en-IN',
        )
        const readiness = await ensureBrowserOnDeviceRecognition(SpeechRecognition, localeCandidates)
        if (disposed) return
        if (readiness.available) {
          locale = readiness.locale
          useBrowserOnDevice = true
          if (readiness.installedNow) setVoiceModeCaptionError(`Local speech model installed for ${locale}.`)
          console.info('[NOVA STT] Voice Mode provider: browser on-device', locale)
        } else {
          console.info('[NOVA STT] Browser-local STT unavailable; trying native browser recognition before Voicebox:', readiness.reason || readiness.message)
          setVoiceModeCaptionError('On-device browser recognition is unavailable. Trying the browser speech service; Voicebox is the fallback.')
        }
      }

      if (voiceRecognitionMode !== 'auto' && voiceRecognitionMode !== 'online') return

      const startRecognition = () => {
        if (disposed || !shouldRestartRecognition || !voiceModeMicEnabledRef.current || voiceModeRecognitionRef.current) return
        try {
          const recognition = new SpeechRecognition()
          voiceModeRecognitionRef.current = recognition
          recognition.lang = locale
          recognition.continuous = true
          recognition.interimResults = true
          recognition.maxAlternatives = 1
          recognition.processLocally = useBrowserOnDevice

          recognition.onstart = () => {
            if (disposed) return
            voiceModeBrowserRecognitionActiveRef.current = true
            setVoiceModeCaptionError('')
          }

          recognition.onresult = (event) => {
            if (disposed || !voiceModeMicEnabledRef.current) return
            // Ignore speaker loopback while NOVA is talking. An interruption
            // pauses the queue first, after which the user's words are accepted.
            const queue = voicePlaybackQueueRef.current
            if (queue?.isPlaying?.() && !queue?.isPaused?.()) return

            const finalParts = []
            const interimParts = []
            for (let index = event.resultIndex; index < event.results.length; index += 1) {
              const result = event.results[index]
              const words = String(result?.[0]?.transcript || '').trim()
              if (!words) continue
              if (result.isFinal) finalParts.push(words)
              else interimParts.push(words)
            }
            if (finalParts.length) {
              voiceModeBrowserFinalTranscriptRef.current = [
                voiceModeBrowserFinalTranscriptRef.current,
                ...finalParts,
              ].filter(Boolean).join(' ').trim()
            }
            voiceModeBrowserInterimTranscriptRef.current = interimParts.join(' ').trim()
            const visible = normalizeNOVAAssistantNameTranscript([
              voiceModeBrowserFinalTranscriptRef.current,
              voiceModeBrowserInterimTranscriptRef.current,
            ].filter(Boolean).join(' ')).trim()
            if (visible) setVoiceModeTranscript(visible)
          }

          recognition.onerror = (event) => {
            if (disposed || event.error === 'aborted' || event.error === 'no-speech') return
            shouldRestartRecognition = false
            voiceModeBrowserRecognitionActiveRef.current = false
            const messages = {
              'not-allowed': 'The browser could not access the microphone.',
              'service-not-allowed': 'Browser speech recognition is blocked.',
              'audio-capture': 'The browser could not access the microphone.',
              'language-not-supported': 'The selected local speech model is unavailable.',
              network: 'The browser recognition service reported a network error.',
            }
            setVoiceModeCaptionError(`${messages[event.error] || `Browser recognition failed: ${event.error}`}. Voicebox will handle speech recognition.`)
          }

          recognition.onend = () => {
            if (voiceModeRecognitionRef.current === recognition) voiceModeRecognitionRef.current = null
            if (!disposed && shouldRestartRecognition && voiceModeMicEnabledRef.current) {
              restartTimer = window.setTimeout(startRecognition, 280)
            }
          }

          // The standard start() signature is supported across Chromium browsers.
          // The VAD continues to capture WAV segments for Voicebox fallback.
          recognition.start()
          voiceModeRecognitionRef.current = recognition
          voiceModeBrowserRecognitionActiveRef.current = true
        } catch (error) {
          shouldRestartRecognition = false
          voiceModeBrowserRecognitionActiveRef.current = false
          setVoiceModeCaptionError(`${error instanceof Error ? error.message : 'Could not start browser recognition'}. Voicebox will handle speech recognition.`)
        }
      }

      voiceModeRecognitionStartRef.current = startRecognition
      startRecognition()
    }

    const flushBrowserUtterance = async (wavBlob) => {
      // VAD fires after its end-of-speech silence window. Give the browser a short
      // grace period to deliver its final result before using Voicebox fallback.
      await new Promise((resolve) => window.setTimeout(resolve, 180))
      if (disposed || !voiceModeOpenRef.current) return
      const browserText = [
        voiceModeBrowserFinalTranscriptRef.current,
        voiceModeBrowserInterimTranscriptRef.current,
      ].filter(Boolean).join(' ').trim()
      voiceModeBrowserFinalTranscriptRef.current = ''
      voiceModeBrowserInterimTranscriptRef.current = ''
      if (browserText) {
        console.info('[NOVA STT] Voice Mode provider: browser recognition', voiceRecognitionMode === 'auto' ? '(on-device)' : '(online)')
        await handleContinuousBrowserTranscript(browserText)
      } else {
        // Browser recognition was technically available but did not return a
        // transcript for this phrase. Voicebox processes the captured audio.
        console.info('[NOVA STT] Voice Mode provider fallback: Voicebox Whisper')
        await handleContinuousVoiceUtterance(wavBlob)
      }
    }

    const startCapture = async () => {
      try {
        capture = await startVoiceActivityCapture({
          isEnabled: () => voiceModeMicEnabledRef.current,
          onStream: (stream) => {
            if (disposed) return
            voiceModeStreamRef.current = stream
            stream.getAudioTracks().forEach((track) => {
              track.enabled = voiceModeMicEnabledRef.current
            })
          },
          onLevel: (level) => {
            if (disposed) return
            voiceOrbLevelRef.current = voiceModeMicEnabledRef.current ? level : 0
          },
          onSpeechStart: () => {
            if (disposed || !voiceModeMicEnabledRef.current) return
            setVoiceModeCaptionError('')
            const queue = voicePlaybackQueueRef.current
            const shouldPauseForInterruption = voiceAutomaticInterruptionEnabledRef.current
            const paused = Boolean(shouldPauseForInterruption && queue?.pause?.())
            voiceInterruptionPendingRef.current = paused
            setVoiceRoomStatus(paused ? 'interrupted' : 'listening')
          },
          onUtterance: async (wavBlob) => {
            if (disposed) return
            if (voiceModeBrowserRecognitionActiveRef.current) {
              await flushBrowserUtterance(wavBlob)
            } else {
              await handleContinuousVoiceUtterance(wavBlob)
            }
          },
          onError: (error) => {
            if (disposed) return
            console.warn('NOVA continuous voice capture:', error)
            setVoiceModeCaptionError(error instanceof Error ? error.message : 'Voice activity detection encountered an error.')
          },
        })

        if (disposed) {
          await capture.stop()
          capture = null
          return
        }
        voiceActivityCaptureRef.current = capture
        voiceModeStreamRef.current = capture.stream
        voiceModeAudioContextRef.current = capture.audioContext
        capture.setEnabled(voiceModeMicEnabledRef.current)
        voiceOrbLevelRef.current = 0
        setVoiceRoomStatus(voiceModeMicEnabledRef.current ? 'ready' : 'muted')

        if (voiceRecognitionMode === 'auto' || voiceRecognitionMode === 'online') {
          await startBrowserRecognition()
          if (disposed) return
          if (!voiceModeBrowserRecognitionActiveRef.current && voiceModeMicEnabledRef.current) {
            setVoiceRoomStatus('ready')
          }
        }
      } catch (error) {
        if (disposed) return
        console.warn('NOVA continuous voice microphone could not start:', error)
        const denied = error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError'
        setVoiceModeCaptionError(error instanceof Error ? error.message : 'Could not start continuous microphone listening.')
        setVoiceRoomStatus(denied ? 'permission' : 'unavailable')
        voiceOrbLevelRef.current = -1
      }
    }

    void startCapture()
    return () => {
      disposed = true
      shouldRestartRecognition = false
      if (restartTimer) window.clearTimeout(restartTimer)
      const recognition = voiceModeRecognitionRef.current
      voiceModeRecognitionRef.current = null
      voiceModeRecognitionStartRef.current = null
      voiceModeBrowserRecognitionActiveRef.current = false
      try { recognition?.abort?.() } catch (error) { console.debug('NOVA browser recognition cleanup:', error) }
      voiceModeBrowserFinalTranscriptRef.current = ''
      voiceModeBrowserInterimTranscriptRef.current = ''
      voiceInterruptionPendingRef.current = false
      if (voiceActivityCaptureRef.current === capture) voiceActivityCaptureRef.current = null
      if (voiceModeStreamRef.current === capture?.stream) voiceModeStreamRef.current = null
      if (voiceModeAudioContextRef.current === capture?.audioContext) voiceModeAudioContextRef.current = null
      if (capture) void capture.stop().catch((error) => console.debug('NOVA voice capture cleanup:', error))
      voiceOrbLevelRef.current = -1
    }
  }, [voiceModeOpen, voiceCaptureRetryNonce, voiceRecognitionMode, conversationLanguage])

  // NOVA accent tooltips: replace browser-native title bubbles with one
  // consistent, accent-coloured tooltip for mouse and keyboard navigation.
  useEffect(() => {
    const appRoot = document.querySelector('.app')
    if (!appRoot) return undefined

    const tooltip = document.createElement('div')
    tooltip.className = 'nova-accent-tooltip'
    tooltip.id = 'nova-accent-tooltip'
    tooltip.setAttribute('role', 'tooltip')
    appRoot.appendChild(tooltip)

    let activeTarget = null
    let previousDescribedBy = null

    const findTooltipTarget = (target) => (
      target instanceof Element ? target.closest('[data-nova-tooltip]') : null
    )

    const positionTooltip = () => {
      if (!activeTarget || !activeTarget.isConnected) return
      const rect = activeTarget.getBoundingClientRect()
      const placeBelow = rect.top < 58
      tooltip.dataset.placement = placeBelow ? 'bottom' : 'top'
      tooltip.style.left = `${Math.min(window.innerWidth - 14, Math.max(14, rect.left + rect.width / 2))}px`
      tooltip.style.top = `${placeBelow ? rect.bottom + 10 : rect.top - 10}px`
    }

    const hideTooltip = (target) => {
      if (!activeTarget || (target && target !== activeTarget)) return
      if (previousDescribedBy) activeTarget.setAttribute('aria-describedby', previousDescribedBy)
      else activeTarget.removeAttribute('aria-describedby')
      activeTarget = null
      previousDescribedBy = null
      tooltip.classList.remove('is-visible')
    }

    const showTooltip = (target) => {
      if (!target || activeTarget === target) return
      const label = (target.getAttribute('data-nova-tooltip') || '').trim()
      if (!label) return
      if (activeTarget) hideTooltip(activeTarget)
      activeTarget = target
      previousDescribedBy = target.getAttribute('aria-describedby')
      tooltip.textContent = label
      target.setAttribute('aria-describedby', 'nova-accent-tooltip')
      positionTooltip()
      tooltip.classList.add('is-visible')
    }

    const handlePointerOver = (event) => {
      const target = findTooltipTarget(event.target)
      if (target && target !== activeTarget) showTooltip(target)
    }
    const handlePointerOut = (event) => {
      const target = findTooltipTarget(event.target)
      const nextTarget = findTooltipTarget(event.relatedTarget)
      if (target && target === activeTarget && nextTarget !== target) hideTooltip(target)
    }
    const handleFocusIn = (event) => showTooltip(findTooltipTarget(event.target))
    const handleFocusOut = (event) => {
      const target = findTooltipTarget(event.target)
      const nextTarget = findTooltipTarget(event.relatedTarget)
      if (target && target === activeTarget && nextTarget !== target) hideTooltip(target)
    }

    // A tooltip trigger can disappear immediately (for example, when Voice
    // Mode closes). In that case browsers do not always dispatch pointerout,
    // so explicitly dismiss the floating tooltip when its trigger is removed.
    const tooltipTargetObserver = new MutationObserver(() => {
      if (activeTarget && !activeTarget.isConnected) hideTooltip(activeTarget)
    })
    tooltipTargetObserver.observe(appRoot, { childList: true, subtree: true })

    appRoot.addEventListener('pointerover', handlePointerOver)
    appRoot.addEventListener('pointerout', handlePointerOut)
    appRoot.addEventListener('focusin', handleFocusIn)
    appRoot.addEventListener('focusout', handleFocusOut)
    window.addEventListener('resize', positionTooltip)
    window.addEventListener('scroll', positionTooltip, true)

    return () => {
      appRoot.removeEventListener('pointerover', handlePointerOver)
      appRoot.removeEventListener('pointerout', handlePointerOut)
      appRoot.removeEventListener('focusin', handleFocusIn)
      appRoot.removeEventListener('focusout', handleFocusOut)
      window.removeEventListener('resize', positionTooltip)
      window.removeEventListener('scroll', positionTooltip, true)
      tooltipTargetObserver.disconnect()
      if (activeTarget) hideTooltip(activeTarget)
      tooltip.remove()
    }
  }, [])

  useEffect(() => {
    let disposed = false
    const checkBackend = async () => {
      try {
        const [statusResponse, capabilitiesResponse] = await Promise.all([
          fetch('http://127.0.0.1:8000/api/status'),
          fetch('http://127.0.0.1:8000/api/capabilities'),
        ])
        if (!statusResponse.ok) throw new Error('Backend unavailable')
        const statusData = await statusResponse.json()
        let capabilitiesData = null
        if (capabilitiesResponse.ok) {
          capabilitiesData = await capabilitiesResponse.json()
        }
        if (!disposed) {
          setBackendOnline(true)
          setSystemSnapshot({ status: statusData, ...(capabilitiesData || {}) })
        }
      } catch {
        if (!disposed) setBackendOnline(false)
      }
    }

    checkBackend()
    const timer = window.setInterval(checkBackend, 3000)
    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [])

  return (
<div
  className={`app ${darkMode ? 'dark-mode' : ''}`}
  data-chat-ui-version="1.9"
  data-accent-theme={accentTheme}
      style={{
        '--sidebar-width': `${sidebarCollapsed ? 72 : sidebarWidth}px`,
        '--nova-accent-primary': selectedAccent.primary,
        '--nova-accent-hover': selectedAccent.hover,
        '--nova-accent-light': selectedAccent.light,
        '--nova-accent-highlight': selectedAccent.highlight,
        '--nova-accent-soft': selectedAccent.soft,
        '--nova-sidebar-bg': selectedAccent.sidebar,
        '--nova-sidebar-curve-back': selectedAccent.curveBack,
        '--nova-sidebar-curve-front': selectedAccent.curveFront,
      }}
    >

      {/* ================= SIDEBAR ================= */}

      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${!sidebarCollapsed && sidebarWidth < 180 ? 'compact' : ''}`}>
        <svg
          className="sidebar-curves"
          viewBox="0 0 207 700"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            className="sidebar-curve-back"
            d="M0 420 C45 444 82 470 104 510 C129 556 138 595 207 624 L207 700 L0 700Z"
          />
          <path
            className="sidebar-curve-front"
            d="M0 665 C17 627 57 614 94 622 C145 633 171 677 207 713 L207 700 L0 700Z"
          />
        </svg>

        <div className="sidebar-top">
          <div className="brand">
            <div className="nova-logo"><span></span></div>
            <span className="nova-text">N O V A</span>
          </div>
        </div>

        <div className="sidebar-primary">
          <button
            type="button"
            className="nav-item nova-glow-host"
            onClick={() => {
              if (activeSection === 'chat') {
                createNewChat()
                return
              }
              setActiveChatId(null)
              setActiveSection('home')
              setTask('')
              setStatusMessage('')
              setActivityMessage('Ready for your next request.')
            }}
            aria-label={activeSection === 'chat' ? 'New chat' : 'Home'}
          >
            <GlowingEffect proximity={82} spread={78} borderWidth={1.2} halo={false} />
            <span className="nav-icon">{activeSection === 'chat' ? <NewChatIcon /> : <HomeIcon />}</span>
            <span className="nav-label">{activeSection === 'chat' ? 'New Chat' : 'Home'}</span>
          </button>
        </div>

        <div className="sidebar-chats">
          <div className={`sidebar-chats-heading ${chatSearchOpen ? 'search-open' : ''}`}>
            {chatSearchOpen ? (
              <>
                <div className="sidebar-chat-search-wrap">
                  <input
                    className="sidebar-chat-search-input"
                    value={chatSearchQuery}
                    onChange={(event) => setChatSearchQuery(event.target.value)}
                    placeholder="Search chats…"
                    aria-label="Search all conversations"
                    autoFocus
                    onKeyDown={(event) => { if (event.key === 'Escape') { setChatSearchOpen(false); setChatSearchQuery('') } }}
                  />
                  <button type="button" className="sidebar-chat-search-close" onClick={() => { setChatSearchOpen(false); setChatSearchQuery('') }} aria-label="Close chat search">×</button>
                </div>
              </>
            ) : (
              <>
                <span className="nav-label">Chats</span>
                <button type="button" className="sidebar-chat-search-toggle" onClick={() => setChatSearchOpen(true)} aria-label="Search conversations" title="Search conversations">
                  <SearchIcon />
                </button>
              </>
            )}
          </div>
          <div className="sidebar-chat-list">
            {visibleChats.length === 0 ? (
              <div className="sidebar-chat-empty nav-label">{normalizedChatSearch ? 'No matching conversations.' : 'Your conversations will appear here.'}</div>
            ) : visibleChats.map((chat) => (
              <div className={`sidebar-chat-item ${activeChatId === chat.id ? 'active' : ''}`} key={chat.id}>
                <button type="button" className="sidebar-chat-select" onClick={() => openChat(chat.id)}>
                  <span className="sidebar-chat-title">{chat.title || 'Chat'}</span>
                  <span className="sidebar-chat-title-compact">{getChatInitials(chat.title || 'Chat')}</span>
                </button>
                <button type="button" className="sidebar-chat-delete" onClick={() => deleteChat(chat.id)} aria-label={`Delete ${chat.title || 'chat'}`}>×</button>
              </div>
            ))}
          </div>
        </div>

        <div className="sidebar-bottom">
          <div className="profile-wrap">
            <div className="sidebar-profile-row">
              <button
                type="button"
                className={`sidebar-profile-button sidebar-settings-profile-button ${activeSection === 'settings' ? 'active' : ''}`}
                onClick={() => setActiveSection('settings')}
                aria-label={`Open Settings for ${userName || 'Omkar'}`}
                aria-current={activeSection === 'settings' ? 'page' : undefined}
              >
                <span className="sidebar-profile-avatar">{getInitials(userName)}</span>
                <span className="sidebar-profile-name nav-label">{userName || 'Omkar'}</span>
                <span className="sidebar-profile-inline-gear" aria-hidden="true"><SettingsIcon /></span>
              </button>
            </div>
          </div>
        </div>

        <div
          className="sidebar-resize-handle"
          onPointerDown={resizeSidebar}
          role="separator"
          aria-label="Resize sidebar"
          aria-orientation="vertical"
        />
      </aside>


      {/* ================= MAIN ================= */}

      <main className={`main ${activeSection === 'chat' ? 'is-chat-view' : ''}`}>

        {activeSection === 'home' && (
          <>
          {/* Photo */}

        <div className="hero-image">
          <img src={heroPhoto} alt="" />
        </div>


        {/* Organic main curve */}

        <svg
          className="organic-main"
          viewBox="0 0 1329 620"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            d="
              M0 0
              L430 0
              C428 91
                438 163
                475 224
              C520 290
                585 334
                650 371
              C715 409
                765 438
                795 477
              C812 501
                820 530
                825 620
              L0 620
              Z
            "
          />
        </svg>


          </>
        )}


        {activeSection === 'home' && (
          <div className="image-message">

            <div className="message-line"></div>

            <div>
              <span>See.</span>
              <span>Understand.</span>
              <span>Act.</span>
              <span>For you.</span>
            </div>

          </div>
        )}


        {/* ================= MAIN CONTENT ================= */}

        {activeSection === 'home' ? (
        <section className="hero">

          <p className="eyebrow">
            YOUR BROWSER. AMPLIFIED.
          </p>

          <h1>
            Hello,<br />
            <span>{getFirstName(userName)}.</span>
          </h1>

          <p className="hero-description">
            Tell me what you need from the web.<br />
            NOVA will plan the next steps.
          </p>


          {/* Command bar */}

          <div
            className={`task-box ${listening || localTranscribing ? 'voice-active' : ''}`}
          >
            {listening ? (
              <div className="voice-capture">
                <div className="voice-capture-copy">
                  <div className="voice-capture-title-row">
                    <span className="voice-capture-dot" />
                    <strong>Listening</strong>
                    <span className="voice-capture-mode">{(activeVoiceInputMode === 'local' || activeVoiceInputMode === 'browser-local') ? 'ON-DEVICE' : 'ONLINE'}</span>
                  </div>
                  <span className="voice-capture-transcript">{voiceLiveTranscript || 'Speak naturally — NOVA is listening.'}</span>
                </div>
                <VoiceBars levels={voiceLevels} active />
                <button type="button" className="voice-finish-button" onClick={toggleVoiceInput}>
                  Done
                </button>
              </div>
            ) : localTranscribing ? (
              <div className="voice-transcribing"><span className="voice-transcribing-spinner" /> Transcribing your voice…</div>
            ) : (
              <>
                <input
                  value={task}
                  onChange={(e) => updateTaskDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void runTask()
                    }
                  }}
                  placeholder="Ask me to do anything..."
                />
                <button
                  className="microphone"
                  aria-label="Start voice input"

                  type="button"
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    toggleVoiceInput()
                  }}
                >
                  <MicIcon />
                </button>
              </>
            )}

            {localRetryAvailable && (
              <button
                type="button"
                className="voice-retry-button"
                onClick={retryVoiceLocally}
                disabled={localTranscribing}
                aria-label="Retry transcription using the local Voicebox engine"

              >
                {localTranscribing ? <span className="voice-retry-spinner" aria-hidden="true" /> : <VoiceRetryIcon />}
                <span>{localTranscribing ? 'Retrying locally…' : 'Retry locally'}</span>
              </button>
            )}

            {!listening && !localTranscribing && (
              <button
                type="button"
                className={`send-button ${taskStarting ? 'is-starting' : ''} ${!task.trim() && !running && !stopArmed ? 'is-voice-entry' : ''}`}
                onClick={handleActionButton}
                disabled={taskStarting}
                aria-label={taskStarting ? 'Starting task' : running ? 'Stop task' : stopArmed ? 'Close NOVA agent' : task.trim() ? 'Send task' : 'Open voice mode'}
              >
                {taskStarting ? <span className="send-spinner" /> : running || stopArmed ? <StopSquareIcon /> : task.trim() ? <SendArrowIcon /> : <VoiceModeIcon />}
              </button>
            )}

          </div>

          <div className={`backend-status ${backendOnline ? 'online' : ''} ${(voiceNotice || statusMessage) ? 'visible' : ''}`}>
            <span className="backend-dot"></span>
            <span>{voiceNotice || statusMessage || (backendOnline ? 'NOVA backend ready' : 'Backend not connected')}</span>
          </div>


          {/* Quick actions */}

          <div className="suggestions">

            <button className="nova-glow-host" onClick={() => setTask('Clean up my downloads')}>
              <GlowingEffect proximity={78} spread={82} borderWidth={1.15} halo={false} />
              <FolderIcon />
              Clean up my downloads
            </button>

            <button className="nova-glow-host" onClick={() => setTask('Summarize this document')}>
              <GlowingEffect proximity={78} spread={82} borderWidth={1.15} halo={false} />
              <FileIcon />
              Summarize this document
            </button>

            <button className="nova-glow-host" onClick={() => setTask('Plan my day')}>
              <GlowingEffect proximity={78} spread={82} borderWidth={1.15} halo={false} />
              <CalendarIcon />
              Plan my day
            </button>

            <button className="nova-glow-host" onClick={() => setTask('Open my design app')}>
              <GlowingEffect proximity={78} spread={82} borderWidth={1.15} halo={false} />
              <GridIcon />
              Open my design app
            </button>

          </div>



        </section>
        ) : activeSection === 'chat' ? (
          <section className="section-page chat-page">
            <div className="chat-conversation-panel chat-conversation-focused chat-workspace">
              {(activeChat || taskStarting || running) ? (
                <div className="conversation-messages" ref={conversationMessagesRef}>
                  {activeChatMessages.map((message, index) => {
                    const messageKey = `${message.time || 'message'}-${index}`
                    const isAssistant = message.role !== 'user'
                    const isSpeaking = speakingMessageKey === messageKey
                    const isGeneratingSpeech = speechBusyMessageKey === messageKey
                    const isTypewriterTarget = Boolean(typewriterTarget && typewriterTarget.chatId === activeChatId && index === latestAssistantMessageIndex && String(message.content || '') === typewriterTarget.content)
                    return (
                      <div
                        className={`conversation-message ${message.role === 'user' ? 'user' : 'nova'}`}
                        key={messageKey}
                      >
                        <p style={{ whiteSpace: 'pre-wrap' }}>
                          {isTypewriterTarget ? (
                            <ResponseStream
                              key={typewriterTarget.nonce}
                              textStream={String(message.content || '')}
                              mode="typewriter"
                              speed={20}
                              as="span"
                              renderText={renderMessageContent}
                            />
                          ) : renderMessageContent(message.content)}
                        </p>
                        {isAssistant && (
                          <div className="nova-response-actions" role="group" aria-label="Response actions">
                            <button
                              type="button"
                              className={`nova-response-action ${copiedMessageKey === messageKey ? 'is-confirmed' : ''}`}
                              onClick={() => void copyResponse(message.content, messageKey)}
                              aria-label={copiedMessageKey === messageKey ? 'Copied response' : 'Copy response'}
                              data-nova-tooltip={copiedMessageKey === messageKey ? 'Copied' : 'Copy response'}
                            >
                              <CopyResponseIcon />
                            </button>
                            <button
                              type="button"
                              className={`nova-response-action ${isSpeaking ? 'is-active' : ''}`}
                              onClick={() => void readAloudResponse(message.content, messageKey)}
                              aria-label={isGeneratingSpeech ? 'Stop speech generation' : isSpeaking ? 'Stop reading aloud' : 'Read aloud'}
                              data-nova-tooltip={isGeneratingSpeech ? 'Preparing speech…' : isSpeaking ? 'Stop reading aloud' : 'Read aloud'}
                              disabled={Boolean(speechBusyMessageKey && speechBusyMessageKey !== messageKey)}
                            >
                              {isGeneratingSpeech ? <span className="nova-response-spinner" aria-hidden="true" /> : <ReadAloudIcon active={isSpeaking} />}
                            </button>
                          </div>
                        )}
                      </div>
                    )
                  })}
                  {(taskStarting || running || pendingApproval) && (
                    <div className="nova-thinking-inline" role="status" aria-live="polite">
                      <span className="nova-thinking-indicator" aria-hidden="true"><i /><i /><i /></span>
                      <div className="nova-thinking-copy">
                        <strong>{pendingApproval ? 'Waiting for your approval' : taskStarting ? 'Getting NOVA ready…' : activityMessage || 'Thinking…'}</strong>
                        <span>
                          {systemSnapshot?.status?.model ? `Using ${systemSnapshot.status.model}` : 'Using NOVA local model'}
                          {activityAgent ? ` · ${activityAgent}` : ''}
                        </span>
                      </div>
                    </div>
                  )}
                  {speechError && <div className="nova-speech-error" role="status">{speechError}</div>}
                </div>
              ) : (
                <div className="conversation-empty">
                  <div className="conversation-empty-mark">O</div>
                  <h2>Start a new conversation.</h2>
                  <p>Send a message below and NOVA will keep the conversation together.</p>
                </div>
              )}

              <div
                className={`task-box chat-task-box ${listening || localTranscribing ? 'voice-active' : ''}`}
              >
                {listening ? (
                  <div className="voice-capture">
                    <div className="voice-capture-copy">
                      <div className="voice-capture-title-row">
                        <span className="voice-capture-dot" />
                        <strong>Listening</strong>
                        <span className="voice-capture-mode">{(activeVoiceInputMode === 'local' || activeVoiceInputMode === 'browser-local') ? 'ON-DEVICE' : 'ONLINE'}</span>
                      </div>
                      <span className="voice-capture-transcript">{voiceLiveTranscript || 'Speak naturally — NOVA is listening.'}</span>
                    </div>
                    <VoiceBars levels={voiceLevels} active />
                    <button type="button" className="voice-finish-button" onClick={toggleVoiceInput}>
                      Done
                    </button>
                  </div>
                ) : localTranscribing ? (
                  <div className="voice-transcribing"><span className="voice-transcribing-spinner" /> Transcribing your voice…</div>
                ) : (
                  <>
                    <input
                      value={task}
                      onChange={(e) => updateTaskDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          void runTask()
                        }
                      }}
                      placeholder={activeChat ? 'Continue this conversation...' : 'Start a new conversation...'}
                    />
                    <button
                      className="microphone"
                      aria-label="Start voice input"

                      type="button"
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        toggleVoiceInput()
                      }}
                    >
                      <MicIcon />
                    </button>
                  </>
                )}
                {localRetryAvailable && (
                  <button
                    type="button"
                    className="voice-retry-button"
                    onClick={retryVoiceLocally}
                    disabled={localTranscribing}
                    aria-label="Retry transcription using the local Voicebox engine"

                  >
                    {localTranscribing ? <span className="voice-retry-spinner" aria-hidden="true" /> : <VoiceRetryIcon />}
                    <span>{localTranscribing ? 'Retrying locally…' : 'Retry locally'}</span>
                  </button>
                )}
                {!listening && !localTranscribing && (
                  <button
                    className={`send-button ${taskStarting ? 'is-starting' : ''} ${!task.trim() && !running && !stopArmed ? 'is-voice-entry' : ''}`}
                    onClick={handleActionButton}
                    disabled={taskStarting}
                    aria-label={taskStarting ? 'Starting task' : running ? 'Stop task' : stopArmed ? 'Close NOVA agent' : task.trim() ? 'Send message' : 'Open voice mode'}
                    type="button"
                  >
                    {taskStarting ? <span className="send-spinner" /> : running || stopArmed ? <StopSquareIcon /> : task.trim() ? <SendArrowIcon /> : <VoiceModeIcon />}
                  </button>
                )}
              </div>
              {voiceNotice && !listening && !localTranscribing && (
                <div className={`voice-feedback ${voiceTranscriptReady ? 'ready' : 'error'}`} role="status">
                  <span className="voice-feedback-mark">{voiceTranscriptReady ? '✓' : '!'}</span>
                  {voiceNotice}
                </div>
              )}

            </div>
          </section>
        ) : (
          <section className="section-page settings-page">
            <p className="eyebrow">NOVA PREFERENCES</p>
            <h1>Settings.</h1>

            <div className="settings-tabs" role="tablist" aria-label="Settings sections">
              <button type="button" role="tab" aria-selected={settingsTab === 'display'} className={settingsTab === 'display' ? 'active' : ''} onClick={() => setSettingsTab('display')}>General</button>
              <button type="button" role="tab" aria-selected={settingsTab === 'speech'} className={settingsTab === 'speech' ? 'active' : ''} onClick={() => setSettingsTab('speech')}>Voice & Speech</button>
              <button type="button" role="tab" aria-selected={settingsTab === 'advanced'} className={settingsTab === 'advanced' ? 'active' : ''} onClick={() => setSettingsTab('advanced')}>Advanced</button>
            </div>

            <div className="settings-panel settings-tab-panel">
              {settingsTab === 'display' && (
                <div className="settings-tab-content" role="tabpanel">
                  <section className="settings-card settings-language-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">GENERAL</span>
                      <h2>Conversation language</h2>
                      <p>Set the language NOVA uses across speech recognition, Qwen responses and Voicebox speech. Automatic follows the language you speak. Your choice is saved on this device.</p>
                    </div>
                    <div className="settings-language-control">
                      <select
                        className="settings-language-select"
                        value={conversationLanguage}
                        onChange={(event) => setConversationLanguage(normalizeConversationLanguage(event.target.value, 'en'))}
                        aria-label="NOVA conversation language"
                      >
                        {NOVA_CONVERSATION_LANGUAGES.map((language) => (
                          <option key={language.code} value={language.code}>{language.label}</option>
                        ))}
                      </select>
                      <small>{NOVA_CONVERSATION_LANGUAGES.find((language) => language.code === conversationLanguage)?.description}</small>
                    </div>
                  </section>

                  <section className="settings-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">PROFILE</span>
                      <h2>Display name</h2>
                      <p>This name is used across your NOVA interface.</p>
                    </div>
                    <input className="settings-name-input" value={nameDraft} onChange={(e) => updateUserName(e.target.value)} placeholder="Enter your name" aria-label="Display name" />
                  </section>

                  <section className="settings-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">APPEARANCE</span>
                      <h2>Theme</h2>
                      <p>Choose how NOVA looks on this device.</p>
                    </div>
                    <div className="settings-theme-options">
                      <button type="button" className={themeMode === 'light' ? 'selected' : ''} onClick={() => setThemeMode('light')}>☼ <span>Light</span></button>
                      <button type="button" className={themeMode === 'dark' ? 'selected' : ''} onClick={() => setThemeMode('dark')}>☾ <span>Dark</span></button>
                      <button type="button" className={themeMode === 'system' ? 'selected' : ''} onClick={() => setThemeMode('system')}>◐ <span>System</span></button>
                    </div>
                  </section>

                  <section className="settings-card settings-accent-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">PERSONALISATION</span>
                      <h2>Accent colour</h2>
                      <p>Choose a colour for NOVA’s sidebar, buttons, chat bubbles and highlights.</p>
                    </div>
                    <div className="accent-theme-options" role="group" aria-label="Choose NOVA accent colour">
                      {ACCENT_THEMES.map((theme) => (
                        <button key={theme.id} type="button" className={`accent-theme-option ${accentTheme === theme.id ? 'selected' : ''}`} onClick={() => setAccentTheme(theme.id)} aria-label={`${theme.name} accent colour`} aria-pressed={accentTheme === theme.id} style={{ '--swatch-color': theme.primary, '--swatch-light': theme.light }}>
                          <span className="accent-theme-swatch">{accentTheme === theme.id ? '✓' : ''}</span>
                          <span className="accent-theme-name">{theme.name}</span>
                        </button>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {settingsTab === 'speech' && (
                <div className="settings-tab-content" role="tabpanel">
                  <section className="settings-card settings-voice-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">VOICE INPUT</span>
                      <h2>Speech recognition</h2>
                      <p>Auto tries this browser's on-device speech recognition first. If unavailable, NOVA tries the browser's regular speech service (which may be network-backed), then falls back to Voicebox Whisper. Voicebox generates every spoken reply. Compatible with Microsoft Edge, Chrome and Brave through capability detection and fallback.</p>
                    </div>
                    <div className="settings-voice-options" role="group" aria-label="Speech recognition mode">
                      <button type="button" className={`settings-voice-option ${voiceRecognitionMode === 'auto' ? 'selected' : ''}`} onClick={() => setVoiceRecognitionMode('auto')} aria-pressed={voiceRecognitionMode === 'auto'} data-tooltip="Tries browser on-device speech recognition first. If unavailable, tries the browser's standard speech service (may be network-backed); if that fails, falls back to Voicebox Whisper. Voicebox remains the TTS engine.">Auto</button>
                      <button type="button" className={`settings-voice-option ${voiceRecognitionMode === 'local' ? 'selected' : ''}`} onClick={() => setVoiceRecognitionMode('local')} aria-pressed={voiceRecognitionMode === 'local'} data-tooltip="Uses Voicebox Whisper for speech-to-text. Voicebox also speaks NOVA replies.">Voicebox</button>
                      <button type="button" className={`settings-voice-option ${voiceRecognitionMode === 'online' ? 'selected' : ''}`} onClick={() => setVoiceRecognitionMode('online')} aria-pressed={voiceRecognitionMode === 'online'} data-tooltip="Uses this browser's regular speech-recognition service, which may be network-backed. If unavailable or blocked, NOVA falls back to Voicebox Whisper. Voicebox handles text-to-speech.">Online Recognition</button>
                    </div>
                  </section>

                  <section className="settings-card settings-voice-behaviour-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">VOICE MODE BEHAVIOUR</span>
                      <h2>Conversation controls</h2>
                      <p>Choose how NOVA listens and reacts while Voice Mode is active. These preferences are saved on this device.</p>
                    </div>
                    <div className="settings-voice-behaviour-options">
                      <label className="settings-voice-behaviour-option">
                        <span><strong>Continuous conversation</strong><small>Automatically submit completed speech segments without requiring another click.</small></span>
                        <input type="checkbox" checked={voiceContinuousEnabled} onChange={(event) => setVoiceContinuousEnabled(event.target.checked)} />
                      </label>
                      <label className="settings-voice-behaviour-option">
                        <span><strong>Automatic interruption</strong><small>Pause NOVA's audio when sustained speech is detected, then resume if no clear request is recognised.</small></span>
                        <input type="checkbox" checked={voiceAutomaticInterruptionEnabled} onChange={(event) => setVoiceAutomaticInterruptionEnabled(event.target.checked)} />
                      </label>
                      <label className="settings-voice-behaviour-option">
                        <span><strong>Live captions by default</strong><small>Show your transcript and NOVA's response in the Voice Mode panel.</small></span>
                        <input type="checkbox" checked={voiceCaptionsEnabled} onChange={(event) => setVoiceCaptionsEnabled(event.target.checked)} />
                      </label>
                    </div>
                  </section>

                  <section className="settings-card settings-voice-speed-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">PLAYBACK</span>
                      <h2>Speech speed</h2>
                      <p>Adjust the playback speed for newly generated Voicebox audio. This changes playback in NOVA, not the voice model itself.</p>
                    </div>
                    <div className="settings-voice-speed-settings">
                      <input type="range" min="0.8" max="1.25" step="0.05" value={voiceSpeechSpeed} onChange={(event) => setVoiceSpeechSpeed(Number(event.target.value))} aria-label="NOVA speech speed" />
                      <output>{voiceSpeechSpeed.toFixed(2)}×</output>
                    </div>
                  </section>

                  <section className="settings-card settings-voice-profile-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">VOICE OUTPUT</span>
                      <h2>NOVA voice</h2>
                      <p>Choose a local Voicebox profile. The selected profile is used for Read Aloud and spoken replies to voice-entered commands.</p>
                    </div>
                    <div className="settings-voice-profile-controls">
                      <VoiceProfilePicker
                        profiles={voiceProfiles}
                        value={selectedVoiceProfileId}
                        onValueChange={setSelectedVoiceProfileId}
                        onPreview={previewVoiceProfile}
                        onOpen={loadVoiceProfiles}
                        previewingId={String(speechBusyMessageKey || speakingMessageKey).startsWith('voice-preview-') ? String(speechBusyMessageKey || speakingMessageKey).replace('voice-preview-', '') : ''}
                        loading={voiceProfilesLoading}
                        error={voiceProfilesError}
                      />
                      <button type="button" className="settings-secondary-button" onClick={() => void loadVoiceProfiles()} disabled={voiceProfilesLoading}>Refresh voices</button>
                    </div>
                  </section>

                  <section className="settings-card settings-voice-automation-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">VOICE COMMANDS</span>
                      <h2>Speak replies in Voice Mode</h2>
                      <p>When enabled, NOVA speaks responses to voice-entered commands and uses your selected Voicebox profile. Text replies remain available when speech output is disabled.</p>
                    </div>
                    <button type="button" className={`settings-toggle ${speakVoiceCommandReplies ? 'on' : ''}`} onClick={() => setSpeakVoiceCommandReplies((value) => !value)} role="switch" aria-checked={speakVoiceCommandReplies} aria-label="Speak replies in Voice Mode"><span /></button>
                  </section>
                </div>
              )}

              {settingsTab === 'advanced' && (
                <div className="settings-tab-content" role="tabpanel">
                  <section className="settings-card settings-runtime-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">LOCAL RUNTIME</span>
                      <h2>System status</h2>
                      <p>Live status for NOVA’s local services and active execution.</p>
                    </div>
                    <div className="settings-runtime-grid">
                      <div className="settings-runtime-stat"><span>Backend</span><strong className={backendOnline ? 'runtime-good' : 'runtime-muted'}>{backendOnline ? 'Connected' : 'Offline'}</strong></div>
                      <div className="settings-runtime-stat"><span>Local model</span><strong>{systemSnapshot?.runtime?.model || systemSnapshot?.status?.model || 'Not reported'}</strong></div>
                      <div className="settings-runtime-stat"><span>Browser worker</span><strong>{systemSnapshot?.runtime?.worker_alive ?? systemSnapshot?.status?.workerAlive ? 'Ready' : backendOnline ? 'Starting' : 'Offline'}</strong></div>
                      <div className="settings-runtime-stat"><span>Active specialist</span><strong>{systemSnapshot?.runtime?.active_agent || systemSnapshot?.status?.activeAgent || 'Idle'}</strong></div>
                      <div className="settings-runtime-stat"><span>Browser session</span><strong>{systemSnapshot?.runtime?.browser_open ?? systemSnapshot?.status?.browserOpen ? 'Open' : 'Closed'}</strong></div>
                      <div className="settings-runtime-stat"><span>Build</span><strong>{systemSnapshot?.application?.version || '0.5.0-alpha'}</strong></div>
                    </div>
                  </section>

                  <section className="settings-card settings-agents-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">AGENT SYSTEM</span>
                      <h2>Active agents</h2>
                      <p>These are the specialists currently registered in this NOVA build.</p>
                    </div>
                    <div className="settings-agent-grid">
                      {(systemSnapshot?.agents || []).map((agentProfile) => (
                        <div className="settings-agent-item" key={agentProfile.id}>
                          <span className="settings-agent-indicator" />
                          <div><strong>{agentProfile.name}</strong><span>{agentProfile.description}</span></div>
                          <small>Active</small>
                        </div>
                      ))}
                      {!systemSnapshot?.agents?.length && <p className="settings-agent-empty">Connect to the NOVA backend to load the active agent registry.</p>}
                    </div>
                  </section>

                  <section className="settings-card settings-release-card">
                    <div className="settings-card-copy">
                      <span className="settings-card-label">BUILD INFORMATION</span>
                      <h2>{systemSnapshot?.application?.name || 'NOVA'} · {systemSnapshot?.application?.version || '0.5.0-alpha'}</h2>
                      <p>{systemSnapshot?.application?.build || 'Alpha 0.5 · Phase 4 Professionalisation'} · {systemSnapshot?.application?.channel || 'development'} channel. Browser automation is provided by the dedicated Brave/Playwright worker.</p>
                    </div>
                  </section>
                </div>
              )}
            </div>
          </section>
        )}

      </main>

      {voiceModeOpen && (
        <section
          className="nova-voice-room"
          data-theme={darkMode ? 'dark' : 'light'}
          data-voice-state={voiceOrbState}
          role="dialog"
          aria-modal="true"
          aria-label="NOVA voice mode"
        >
          <header className="nova-voice-room-header">
            <div className="nova-voice-room-brand" aria-label="NOVA">
              <div className="nova-logo"><span /></div>
              <span className="nova-voice-brand-name">NOVA</span>
              <span className="nova-voice-room-tag">VOICE</span>
            </div>

          </header>

          <main className={`nova-voice-room-content ${voiceCaptionsEnabled ? 'has-transcription' : ''}`}>
            <div className="nova-voice-visual">
              <MercuryOrb
                className="nova-mercury-orb"
                state={voiceOrbState}
                size={220}
                colorFrom={selectedAccent.light}
                colorTo={selectedAccent.highlight}
                levelRef={voiceOrbLevelRef}
                label="NOVA voice assistant"
              />
            </div>

            {voiceCaptionsEnabled && (
              <section className="nova-voice-captions-panel" aria-label="Live conversation transcript">
                <div className="nova-voice-captions-heading">
                  <span className="nova-voice-captions-label">LIVE TRANSCRIPT</span>
                  <span className={`nova-voice-caption-live ${voiceModeMicEnabled && !voiceModeCaptionError ? 'is-live' : ''}`}>
                    <i aria-hidden="true" />{voiceModeCaptionError || (!voiceModeMicEnabled ? 'Muted' : 'Live')}
                  </span>
                </div>

                <div className="nova-voice-chat-thread" role="log" aria-live="polite" aria-atomic="false" aria-relevant="additions text">
                  {voiceModeTurns.map((turn) => {
                    const isUser = turn.role === 'you'
                    return (
                      <article className={`nova-voice-chat-message ${isUser ? 'is-user' : 'is-assistant'}`} key={turn.id}>
                        <span className="nova-voice-chat-speaker">{isUser ? 'Me' : 'NOVA'}</span>
                        <div className="nova-voice-chat-bubble"><p>{turn.content}</p></div>
                      </article>
                    )
                  })}
                  {voiceModeTranscript.trim() && (
                    <article className="nova-voice-chat-message is-user is-live-message">
                      <span className="nova-voice-chat-speaker">Me</span>
                      <div className="nova-voice-chat-bubble"><p>{voiceModeTranscript}</p></div>
                    </article>
                  )}
                  {voiceModeAssistantTranscript && !voiceModeTurns.some((turn) => turn.role === 'nova' && turn.content === voiceModeAssistantTranscript) && (
                    <article className="nova-voice-chat-message is-assistant is-live-message">
                      <span className="nova-voice-chat-speaker">NOVA</span>
                      <div className="nova-voice-chat-bubble"><p>{voiceModeAssistantTranscript}</p></div>
                    </article>
                  )}
                  {!voiceModeTurns.length && !voiceModeTranscript.trim() && !voiceModeAssistantTranscript && (
                    <p className="nova-voice-transcript-empty">
                      {voiceRoomStatus === 'thinking' ? 'NOVA is thinking…' : voiceModeCaptionError || 'Your conversation with NOVA will appear here.'}
                    </p>
                  )}
                  <div ref={voiceTranscriptEndRef} aria-hidden="true" />
                </div>
                {voiceModeTranscript.trim() && (
                  <button type="button" className="nova-voice-send-transcript" onClick={submitVoiceModeTranscript} disabled={running || taskStarting}>
                    {running || taskStarting ? 'NOVA is thinking…' : 'Send to NOVA'}
                  </button>
                )}
              </section>
            )}
          </main>

          <footer className="nova-voice-room-footer">
            <div className="nova-voice-status" aria-live="polite">
              <span className="nova-voice-status-dot" />
              <span>{getVoiceStatusLabel(voiceRoomStatus, voiceModeMicEnabled, voiceModeCaptionError)}</span>
            </div>
            {['permission', 'unavailable'].includes(voiceRoomStatus) && (
              <button type="button" className="nova-voice-retry-button" onClick={retryVoiceCapture}>
                Retry microphone connection
              </button>
            )}
            <div className="nova-voice-controls" role="group" aria-label="Voice controls">
              <button
                type="button"
                className={`nova-voice-round-control nova-voice-mute-button ${!voiceModeMicEnabled ? 'is-off' : ''}`}
                onClick={() => setVoiceModeMicEnabled((value) => !value)}
                aria-label={voiceModeMicEnabled ? 'Mute microphone' : 'Unmute microphone'}
                aria-pressed={!voiceModeMicEnabled}
                data-nova-tooltip={voiceModeMicEnabled ? 'Mute microphone' : 'Unmute microphone'}
              >
                <span className="nova-voice-mic-icon">
                  <MicIcon />
                  {!voiceModeMicEnabled && <i aria-hidden="true" />}
                </span>
              </button>

              <button
                type="button"
                className={`nova-voice-round-control nova-voice-captions-button ${voiceCaptionsEnabled ? 'is-active' : ''}`}
                onClick={() => setVoiceCaptionsEnabled((value) => !value)}
                aria-label={voiceCaptionsEnabled ? 'Hide captions' : 'Show captions'}
                aria-pressed={voiceCaptionsEnabled}
                data-nova-tooltip={voiceCaptionsEnabled ? 'Hide captions' : 'Show captions'}
              >
                <CaptionsIcon />
              </button>

              <button
                type="button"
                className="nova-voice-end-button"
                onClick={closeVoiceMode}
                aria-label="End voice mode"
                data-nova-tooltip="End voice mode"
              >
                <span className="nova-voice-end-icon" aria-hidden="true" />
              </button>
            </div>
          </footer>
        </section>
      )}

      {pendingApproval && (
        <div
          role="presentation"
          style={{
            position: 'fixed', inset: 0, zIndex: 10000,
            background: 'rgba(10, 16, 22, 0.58)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="nova-approval-title"
            style={{
              width: 'min(520px, 100%)', borderRadius: 18,
              padding: 24, background: darkMode ? '#20272b' : '#ffffff',
              color: darkMode ? '#f2f5f4' : '#202927',
              boxShadow: '0 24px 80px rgba(0,0,0,.28)',
              border: `1px solid ${darkMode ? '#3d4847' : '#dce5df'}`,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '.08em', opacity: .7 }}>
              NOVA SAFETY CHECK
            </div>
            <h2 id="nova-approval-title" style={{ margin: '8px 0 10px', fontSize: 22 }}>
              Approval required
            </h2>
            <p style={{ lineHeight: 1.55, margin: '0 0 14px' }}>
              NOVA identified a high-impact browser action. It will not proceed until you approve it.
            </p>
            <div style={{
              padding: 14, borderRadius: 12, marginBottom: 12,
              background: darkMode ? '#2b3538' : '#f3f6f3',
              overflowWrap: 'anywhere', lineHeight: 1.5,
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, opacity: .65, marginBottom: 5 }}>PROPOSED ACTION</div>
              <div style={{ fontWeight: 650 }}>{pendingApproval.objective}</div>
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.5, opacity: .78, margin: '0 0 18px' }}>
              {pendingApproval.reason} Only approve this if the action and destination are correct.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                disabled={approvalBusy}
                onClick={() => respondToApproval('deny')}
                style={{
                  border: `1px solid ${darkMode ? '#596664' : '#cbd6cf'}`,
                  borderRadius: 10, padding: '10px 16px', background: 'transparent',
                  color: 'inherit', cursor: approvalBusy ? 'wait' : 'pointer', fontWeight: 650,
                }}
              >Decline</button>
              <button
                type="button"
                disabled={approvalBusy}
                onClick={() => respondToApproval('approve')}
                style={{
                  border: 0, borderRadius: 10, padding: '10px 16px',
                  background: selectedAccent.primary, color: '#fff',
                  cursor: approvalBusy ? 'wait' : 'pointer', fontWeight: 700,
                  opacity: approvalBusy ? .7 : 1,
                }}
              >{approvalBusy ? 'Sending…' : 'Approve action'}</button>
            </div>
            <p style={{ fontSize: 11, opacity: .55, margin: '14px 0 0' }}>
              This request expires after two minutes. Declining or timing out leaves the action unperformed.
            </p>
          </section>
        </div>
      )}

    </div>
  )
}

export default App