import { useEffect, useRef } from 'react'

const LERP = 0.2
const TRAIL_LERP = 0.12
const FLOAT_SPEED = 0.004
const ROTATE_LIMIT = 12
const PULSE_DECAY = 0.9
const CURSOR_SIZE = 40
const MAX_PARTICLES = 20
const BASE_EMIT_INTERVAL = 38
const HOVER_EMIT_INTERVAL = 24
const PARTICLE_COLORS = [
  'rgba(124, 92, 255, 0.34)',
  'rgba(99, 102, 241, 0.28)',
  'rgba(59, 130, 246, 0.24)',
]

function isInteractiveTarget(target) {
  if (!(target instanceof Element)) return false
  return Boolean(
    target.closest(
      'button, a, input, textarea, select, [role="button"], .panel-hover, .glass-panel, .saas-nav-item, .device-history-card, .market-card, .scan-section',
    ),
  )
}

export function AICursor({ imagePath = '/assets/bot.png' }) {
  const cursorRef = useRef(null)
  const trailRef = useRef(null)
  const particleRefs = useRef([])
  const particlesRef = useRef(
    Array.from({ length: MAX_PARTICLES }, () => ({
      active: false,
      x: 0,
      y: 0,
      vx: 0,
      vy: 0,
      size: 0,
      life: 0,
      maxLife: 1,
      color: PARTICLE_COLORS[0],
    })),
  )
  const rafRef = useRef(0)
  const targetRef = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  const cursorPosRef = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  const trailPosRef = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  const lastPosRef = useRef({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  const interactiveRef = useRef(false)
  const clickPulseRef = useRef(0)
  const emitIndexRef = useRef(0)
  const lastEmitRef = useRef(0)
  const lastFrameTimeRef = useRef(0)

  useEffect(() => {
    const supportsFinePointer = window.matchMedia('(pointer: fine)').matches
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!supportsFinePointer || reducedMotion) return undefined

    document.body.classList.add('cursor-ai-enabled')

    const emitParticle = (x, y, options = {}) => {
      const {
        spread = 1,
        speed = 0.12,
        size = 8,
        life = 420,
        color,
      } = options

      const particle = particlesRef.current[emitIndexRef.current]
      emitIndexRef.current = (emitIndexRef.current + 1) % MAX_PARTICLES

      const angle = Math.random() * Math.PI * 2
      const velocity = speed * (0.55 + Math.random() * spread)
      particle.active = true
      particle.x = x
      particle.y = y
      particle.vx = Math.cos(angle) * velocity
      particle.vy = Math.sin(angle) * velocity - 0.02
      particle.size = size * (0.82 + Math.random() * 0.45)
      particle.life = life * (0.82 + Math.random() * 0.3)
      particle.maxLife = particle.life
      particle.color = color || PARTICLE_COLORS[Math.floor(Math.random() * PARTICLE_COLORS.length)]
    }

    const emitBurst = (x, y) => {
      for (let index = 0; index < 8; index += 1) {
        emitParticle(x, y, {
          spread: 1.6,
          speed: 0.22,
          size: 9,
          life: 360,
          color: index % 2 === 0 ? PARTICLE_COLORS[0] : PARTICLE_COLORS[2],
        })
      }
    }

    const handleMouseMove = (event) => {
      targetRef.current.x = event.clientX
      targetRef.current.y = event.clientY
      interactiveRef.current = isInteractiveTarget(event.target)
    }

    const handleMouseOver = (event) => {
      interactiveRef.current = isInteractiveTarget(event.target)
    }

    const handleClick = (event) => {
      const button = event.target instanceof Element ? event.target.closest('button, .primary-button, .secondary-button, .timeframe-button') : null
      clickPulseRef.current = 0.18
      emitBurst(targetRef.current.x, targetRef.current.y)
      if (!button) return
      button.classList.remove('ripple-active')
      // force reflow so repeated clicks retrigger the ripple
      void button.offsetWidth
      button.classList.add('ripple-active')
      window.setTimeout(() => button.classList.remove('ripple-active'), 450)
    }

    const animate = (time) => {
      const lastTime = lastFrameTimeRef.current || time
      const delta = Math.min(32, time - lastTime)
      lastFrameTimeRef.current = time

      const cursorPos = cursorPosRef.current
      const trailPos = trailPosRef.current
      const lastPos = lastPosRef.current
      const target = targetRef.current

      cursorPos.x += (target.x - cursorPos.x) * LERP
      cursorPos.y += (target.y - cursorPos.y) * LERP
      trailPos.x += (cursorPos.x - trailPos.x) * TRAIL_LERP
      trailPos.y += (cursorPos.y - trailPos.y) * TRAIL_LERP

      const dx = cursorPos.x - lastPos.x
      const rotate = Math.max(-ROTATE_LIMIT, Math.min(ROTATE_LIMIT, dx * 2))
      const floatY = Math.sin(time * FLOAT_SPEED) * 2.2
      const breathe = 1 + Math.sin(time * 0.0033) * 0.035
      clickPulseRef.current *= PULSE_DECAY
      const clickPulse = clickPulseRef.current
      const scale = (interactiveRef.current ? 1.14 : 1) * breathe + clickPulse
      const trailScale = interactiveRef.current ? 1.1 : 1
      const emitInterval = interactiveRef.current ? HOVER_EMIT_INTERVAL : BASE_EMIT_INTERVAL

      if (time - lastEmitRef.current >= emitInterval) {
        emitParticle(trailPos.x, trailPos.y, {
          spread: interactiveRef.current ? 1.15 : 0.85,
          speed: interactiveRef.current ? 0.16 : 0.1,
          size: interactiveRef.current ? 8 : 6.5,
          life: interactiveRef.current ? 420 : 360,
        })
        lastEmitRef.current = time
      }

      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate3d(${cursorPos.x}px, ${cursorPos.y + floatY}px, 0) translate(-50%, -50%) rotate(${rotate}deg) scale(${scale})`
        cursorRef.current.style.opacity = '1'
        cursorRef.current.dataset.interactive = interactiveRef.current ? 'true' : 'false'
        cursorRef.current.dataset.clicking = clickPulse > 0.03 ? 'true' : 'false'
      }
      if (trailRef.current) {
        trailRef.current.style.transform = `translate3d(${trailPos.x}px, ${trailPos.y + floatY * 0.55}px, 0) translate(-50%, -50%) scale(${trailScale})`
        trailRef.current.style.opacity = '1'
        trailRef.current.dataset.interactive = interactiveRef.current ? 'true' : 'false'
      }

      particlesRef.current.forEach((particle, index) => {
        const node = particleRefs.current[index]
        if (!node) return

        if (!particle.active || particle.life <= 0) {
          particle.active = false
          node.style.opacity = '0'
          return
        }

        particle.life -= delta
        particle.x += particle.vx * delta
        particle.y += particle.vy * delta
        particle.vx *= 0.985
        particle.vy = (particle.vy * 0.985) - 0.0008 * delta

        const lifeProgress = Math.max(0, particle.life / particle.maxLife)
        const currentSize = Math.max(1.4, particle.size * (0.45 + lifeProgress * 0.55))

        node.style.opacity = String(lifeProgress * (interactiveRef.current ? 0.95 : 0.7))
        node.style.width = `${currentSize}px`
        node.style.height = `${currentSize}px`
        node.style.transform = `translate3d(${particle.x}px, ${particle.y}px, 0) translate(-50%, -50%) scale(${lifeProgress})`
        node.style.background = particle.color
        node.style.boxShadow = `0 0 ${10 + currentSize}px ${particle.color}`
      })

      lastPos.x = cursorPos.x
      lastPos.y = cursorPos.y

      rafRef.current = window.requestAnimationFrame(animate)
    }

    window.addEventListener('mousemove', handleMouseMove, { passive: true })
    window.addEventListener('mouseover', handleMouseOver, { passive: true })
    window.addEventListener('click', handleClick, { passive: true })
    rafRef.current = window.requestAnimationFrame(animate)

    return () => {
      window.cancelAnimationFrame(rafRef.current)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseover', handleMouseOver)
      window.removeEventListener('click', handleClick)
      document.body.classList.remove('cursor-ai-enabled')
    }
  }, [])

  return (
    <>
      <div id="ai-cursor-trail" ref={trailRef} aria-hidden="true" />
      <div className="ai-cursor-particles" aria-hidden="true">
        {particlesRef.current.map((_, index) => (
          <div
            key={`particle-${index}`}
            className="ai-cursor-particle"
            ref={(node) => {
              particleRefs.current[index] = node
            }}
          />
        ))}
      </div>
      <div id="ai-cursor" className="ai-cursor" ref={cursorRef} aria-hidden="true">
        <img src={imagePath} alt="" className="ai-cursor-image" draggable="false" />
      </div>
    </>
  )
}

