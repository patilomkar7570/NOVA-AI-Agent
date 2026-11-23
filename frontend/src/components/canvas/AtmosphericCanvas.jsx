import { useEffect, useRef } from 'react'

/**
 * AtmosphericCanvas
 * Inspired by Active Theory's ambient spatial depth.
 * Renders lightweight, fluid interactive ambient particles and soft glowing light meshes.
 * Reacts to agent execution states, theme, and cursor movement without heavy 3D dependencies.
 */
export default function AtmosphericCanvas({
  darkMode = false,
  accentColor = '#0071e3',
  isGenerating = false,
  interactive = true,
}) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const mouseRef = useRef({ x: -1000, y: -1000, vx: 0, vy: 0, lastX: 0, lastY: 0 })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return

    let width = (canvas.width = window.innerWidth)
    let height = (canvas.height = window.innerHeight)

    const handleResize = () => {
      if (!canvas) return
      width = canvas.width = window.innerWidth
      height = canvas.height = window.innerHeight
    }
    window.addEventListener('resize', handleResize)

    // Reduced motion check
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion) return

    // Particle count: restrained for smooth 60fps performance
    const count = Math.min(38, Math.floor((width * height) / 32000))
    const particles = []

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.45,
        vy: (Math.random() - 0.5) * 0.45,
        radius: Math.random() * 2.5 + 1.2,
        baseAlpha: Math.random() * 0.35 + 0.1,
        phase: Math.random() * Math.PI * 2,
      })
    }

    const handleMouseMove = (e) => {
      if (!interactive) return
      const dx = e.clientX - mouseRef.current.lastX
      const dy = e.clientY - mouseRef.current.lastY
      mouseRef.current.x = e.clientX
      mouseRef.current.y = e.clientY
      mouseRef.current.vx = dx * 0.1
      mouseRef.current.vy = dy * 0.1
      mouseRef.current.lastX = e.clientX
      mouseRef.current.lastY = e.clientY
    }
    window.addEventListener('mousemove', handleMouseMove, { passive: true })

    const render = () => {
      ctx.clearRect(0, 0, width, height)

      // Speed multiplier when agent is generating/reasoning
      const speedMult = isGenerating ? 2.2 : 1.0

      // Render subtle ambient light nodes and connections
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i]

        p.phase += 0.02 * speedMult
        const alpha = p.baseAlpha + Math.sin(p.phase) * 0.1

        p.x += (p.vx + mouseRef.current.vx * 0.05) * speedMult
        p.y += (p.vy + mouseRef.current.vy * 0.05) * speedMult

        // Wrap around boundaries smoothly
        if (p.x < -10) p.x = width + 10
        if (p.x > width + 10) p.x = -10
        if (p.y < -10) p.y = height + 10
        if (p.y > height + 10) p.y = -10

        // Subtle mouse push
        const dx = p.x - mouseRef.current.x
        const dy = p.y - mouseRef.current.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 120 && dist > 0) {
          const force = (1 - dist / 120) * 0.8
          p.x += (dx / dist) * force * 2.5
          p.y += (dy / dist) * force * 2.5
        }

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)

        if (darkMode) {
          ctx.fillStyle = `rgba(180, 215, 255, ${Math.max(0, Math.min(1, alpha * 0.85))})`
          ctx.shadowColor = accentColor
          ctx.shadowBlur = isGenerating ? 8 : 4
        } else {
          ctx.fillStyle = `rgba(70, 95, 120, ${Math.max(0, Math.min(1, alpha * 0.35))})`
          ctx.shadowColor = 'transparent'
          ctx.shadowBlur = 0
        }
        ctx.fill()

        // Soft connective filament between neighboring particles
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j]
          const dist2 = Math.hypot(p.x - p2.x, p.y - p2.y)
          if (dist2 < 95) {
            const lineAlpha = (1 - dist2 / 95) * (darkMode ? 0.12 : 0.05)
            ctx.beginPath()
            ctx.strokeStyle = darkMode ? `rgba(140, 180, 240, ${lineAlpha})` : `rgba(100, 120, 140, ${lineAlpha})`
            ctx.lineWidth = 0.75
            ctx.moveTo(p.x, p.y)
            ctx.lineTo(p2.x, p2.y)
            ctx.stroke()
          }
        }
      }

      // Decay mouse velocity
      mouseRef.current.vx *= 0.92
      mouseRef.current.vy *= 0.92

      animRef.current = requestAnimationFrame(render)
    }

    animRef.current = requestAnimationFrame(render)

    return () => {
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('mousemove', handleMouseMove)
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [darkMode, accentColor, isGenerating, interactive])

  return (
    <canvas
      ref={canvasRef}
      className="nova-atmospheric-canvas"
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
        opacity: darkMode ? 0.85 : 0.6,
        transition: 'opacity 0.4s ease',
      }}
    />
  )
}
