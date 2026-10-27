"use client"

import { useEffect, useRef } from "react"

export function DataFlowBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let animationFrameId: number
    let width = 0
    let height = 0

    // Resize handler
    const handleResize = () => {
      width = window.innerWidth
      height = window.innerHeight
      canvas.width = width
      canvas.height = height
    }
    
    window.addEventListener("resize", handleResize)
    handleResize()

    let mouseX = -1000
    let mouseY = -1000
    let targetMouseX = -1000
    let targetMouseY = -1000

    const handleMouseMove = (e: MouseEvent) => {
      targetMouseX = e.clientX
      targetMouseY = e.clientY
    }

    const handleMouseLeave = () => {
      targetMouseX = -1000
      targetMouseY = -1000
    }

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseleave", handleMouseLeave)

    // Data streams configuration
    const numStreams = Math.floor(width / 25)
    const streams: { baseX: number; x: number; speed: number; y: number; length: number; opacity: number }[] = []

    for (let i = 0; i < numStreams; i++) {
      const startX = Math.random() * width
      streams.push({
        baseX: startX,
        x: startX,
        y: Math.random() * height,
        speed: 1 + Math.random() * 2.5,
        length: 50 + Math.random() * 150,
        opacity: 0.1 + Math.random() * 0.3
      })
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height)

      // Draw structured grid lines
      ctx.strokeStyle = "rgba(16, 185, 129, 0.03)" // Emerald tint
      ctx.lineWidth = 1
      ctx.beginPath()
      for (let i = 0; i < width; i += 40) {
        ctx.moveTo(i, 0)
        ctx.lineTo(i, height)
      }
      for (let i = 0; i < height; i += 40) {
        ctx.moveTo(0, i)
        ctx.lineTo(width, i)
      }
      ctx.stroke()

      // Smooth mouse movement
      mouseX += (targetMouseX - mouseX) * 0.1
      mouseY += (targetMouseY - mouseY) * 0.1

      // Draw mouse glow
      if (mouseX > -500 && mouseY > -500) {
        const glowRadius = 300
        const glow = ctx.createRadialGradient(mouseX, mouseY, 0, mouseX, mouseY, glowRadius)
        glow.addColorStop(0, "rgba(16, 185, 129, 0.12)")
        glow.addColorStop(1, "rgba(16, 185, 129, 0)")
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(mouseX, mouseY, glowRadius, 0, Math.PI * 2)
        ctx.fill()
      }

      // Draw data streams
      streams.forEach((stream) => {
        // Move stream down
        stream.y += stream.speed
        
        // Mouse repel logic
        const dx = stream.x - mouseX
        const dy = stream.y - mouseY
        const dist = Math.sqrt(dx * dx + dy * dy)
        
        if (dist < 250 && mouseX > -500) {
          const repelForce = (250 - dist) / 250
          stream.x += (dx > 0 ? 1 : -1) * repelForce * 3
        }
        
        // Attract back to base X
        stream.x += (stream.baseX - stream.x) * 0.05

        if (stream.y - stream.length > height) {
          stream.y = -stream.length
          stream.baseX = Math.random() * width
          stream.x = stream.baseX
        }

        // Draw the stream (gradient from transparent to bright emerald to transparent)
        const gradient = ctx.createLinearGradient(
          stream.x, stream.y - stream.length, 
          stream.x, stream.y
        )
        gradient.addColorStop(0, "rgba(16, 185, 129, 0)")
        gradient.addColorStop(0.5, `rgba(16, 185, 129, ${stream.opacity})`)
        gradient.addColorStop(1, "rgba(16, 185, 129, 0)")

        ctx.strokeStyle = gradient
        ctx.lineWidth = 2
        ctx.lineCap = "round"
        ctx.beginPath()
        ctx.moveTo(stream.x, stream.y - stream.length)
        ctx.lineTo(stream.x, stream.y)
        ctx.stroke()

        // Draw "data packets" (bright dots at the leading edge)
        ctx.fillStyle = `rgba(16, 185, 129, ${stream.opacity * 2})`
        ctx.beginPath()
        ctx.arc(stream.x, stream.y, 1.5, 0, Math.PI * 2)
        ctx.fill()
      })

      animationFrameId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      window.removeEventListener("resize", handleResize)
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseleave", handleMouseLeave)
      cancelAnimationFrame(animationFrameId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      style={{ opacity: 0.8 }}
    />
  )
}
