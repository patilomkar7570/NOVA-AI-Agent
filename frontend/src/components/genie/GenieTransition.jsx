import { useState, useEffect, useLayoutEffect, useRef, useId, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { computeGeniePath, computeGenieTransform, clamp } from './genieMath'
import './genie.css'

/**
 * GenieTransition Component
 * Provides fluid liquid SVG deformation matching the macOS Genie effect.
 */
export default function GenieTransition({
  isOpen,
  triggerRef,
  triggerRect: explicitTriggerRect,
  onClose,
  mode = 'auto',
  variant = 'modal', // 'modal' | 'popover' | 'fullscreen' | 'drawer'
  backdrop = true,
  duration = 420,
  className = '',
  children,
}) {
  const [phase, setPhase] = useState(isOpen ? 'opening' : 'unmounted')
  const [progress, setProgress] = useState(isOpen ? 1 : 0)
  const [targetRect, setTargetRect] = useState(null)
  const [srcRect, setSrcRect] = useState(null)
  const [reducedMotion, setReducedMotion] = useState(false)

  const clipId = useId().replace(/:/g, '')
  const contentRef = useRef(null)
  const animFrameRef = useRef(null)
  const startTimeRef = useRef(null)
  const [cachedChildren, setCachedChildren] = useState(children)

  useEffect(() => {
    if (children) {
      setCachedChildren(children)
    }
  }, [children])

  // Check reduced motion preference
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReducedMotion(mq.matches)
    const handler = (e) => setReducedMotion(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Resolve trigger rectangle
  const measureTrigger = useCallback(() => {
    if (explicitTriggerRect) return explicitTriggerRect
    if (triggerRef?.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      return {
        x: rect.x,
        y: rect.y,
        w: rect.width,
        h: rect.height,
      }
    }
    // Fallback: bottom center of window
    return {
      x: window.innerWidth / 2 - 24,
      y: window.innerHeight - 70,
      w: 48,
      h: 48,
    }
  }, [triggerRef, explicitTriggerRect])

  // Handle open/close state transitions
  useEffect(() => {
    if (isOpen) {
      const trigger = measureTrigger()
      setSrcRect(trigger)
      if (variant === 'fullscreen') {
        setTargetRect({
          x: 0,
          y: 0,
          w: window.innerWidth,
          h: window.innerHeight,
        })
      }
      setPhase('opening')
      startTimeRef.current = performance.now()
    } else {
      if (phase === 'open' || phase === 'opening') {
        const trigger = measureTrigger()
        setSrcRect(trigger)
        if (variant === 'fullscreen') {
          setTargetRect({
            x: 0,
            y: 0,
            w: window.innerWidth,
            h: window.innerHeight,
          })
        }
        setPhase('closing')
        startTimeRef.current = performance.now()
      }
    }
  }, [isOpen, measureTrigger, variant, phase])

  // Responsive resize sync for fullscreen mode
  useEffect(() => {
    if (variant === 'fullscreen' && phase !== 'unmounted') {
      const handleResize = () => {
        setTargetRect({
          x: 0,
          y: 0,
          w: window.innerWidth,
          h: window.innerHeight,
        })
      }
      window.addEventListener('resize', handleResize)
      return () => window.removeEventListener('resize', handleResize)
    }
  }, [variant, phase])

  // Animation frame loop
  useEffect(() => {
    if (phase !== 'opening' && phase !== 'closing') return

    const animate = (now) => {
      if (!startTimeRef.current) startTimeRef.current = now
      const elapsed = now - startTimeRef.current
      const rawP = clamp(elapsed / duration, 0, 1)

      if (phase === 'opening') {
        setProgress(rawP)
        if (rawP >= 1) {
          setPhase('open')
          return
        }
      } else if (phase === 'closing') {
        const revP = 1 - rawP
        setProgress(revP)
        if (rawP >= 1) {
          setPhase('unmounted')
          return
        }
      }

      animFrameRef.current = requestAnimationFrame(animate)
    }

    animFrameRef.current = requestAnimationFrame(animate)

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
      }
    }
  }, [phase, duration])

  // Measure content target rect synchronously after mounting / layout
  useLayoutEffect(() => {
    if (phase !== 'unmounted') {
      if (variant === 'fullscreen') {
        setTargetRect({
          x: 0,
          y: 0,
          w: window.innerWidth,
          h: window.innerHeight,
        })
      } else if (contentRef.current) {
        const rect = contentRef.current.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) {
          setTargetRect({
            x: rect.x,
            y: rect.y,
            w: rect.width,
            h: rect.height,
          })
        }
      }
    }
  }, [phase, variant])

  // Listen for Escape key
  useEffect(() => {
    if (phase === 'unmounted') return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && onClose) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [phase, onClose])

  if (phase === 'unmounted') return null

  // Compute SVG clipping path and transform
  const isTransitioning = (phase === 'opening' || phase === 'closing') && !reducedMotion
  const activePath = isTransitioning && variant !== 'fullscreen' && srcRect && targetRect
    ? computeGeniePath(srcRect, targetRect, progress, mode)
    : null

  const transformStyle = isTransitioning && srcRect && targetRect
    ? computeGenieTransform(srcRect, targetRect, progress)
    : {}

  const portalContent = (
    <div
      className={`genie-portal variant-${variant} ${phase === 'open' ? 'genie-open' : ''} ${className}`}
      role={variant === 'modal' ? 'dialog' : undefined}
      aria-modal={variant === 'modal' ? 'true' : undefined}
    >
      {/* SVG Defs for ClipPath */}
      {isTransitioning && activePath && (
        <svg className="genie-svg-defs" aria-hidden="true">
          <defs>
            <clipPath id={`genie-clip-${clipId}`} clipPathUnits="userSpaceOnUse">
              <path d={activePath} />
            </clipPath>
          </defs>
        </svg>
      )}

      {/* Dimmed Backdrop */}
      {backdrop && variant !== 'popover' && (
        <div
          className={`genie-backdrop ${phase === 'open' || (phase === 'opening' && progress > 0.05) ? 'visible' : ''}`}
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Surface with SVG Clip & GPU Scaling */}
      <div
        ref={contentRef}
        className="genie-surface-wrapper"
        style={{
          clipPath: isTransitioning && activePath ? `url(#genie-clip-${clipId})` : 'none',
          WebkitClipPath: isTransitioning && activePath ? `url(#genie-clip-${clipId})` : 'none',
          transform: isTransitioning ? `scale(${transformStyle.scale || 1})` : 'none',
          transformOrigin: transformStyle.transformOrigin || 'center center',
          opacity: reducedMotion ? (phase === 'closing' ? 0 : 1) : (transformStyle.opacity ?? 1),
        }}
      >
        {children || cachedChildren}
      </div>
    </div>
  )

  return createPortal(portalContent, document.body)
}
