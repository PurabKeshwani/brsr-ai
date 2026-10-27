"use client"

import { useEffect, useRef } from "react"
import { useInView, useMotionValue, useSpring } from "framer-motion"
import { cn } from "@/lib/utils"

export function AnimatedNumber({
  value,
  className,
  formatter = (v: number) => Math.round(v).toString(),
  delay = 0,
}: {
  value: number;
  className?: string;
  formatter?: (v: number) => string;
  delay?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const motionValue = useMotionValue(0)
  const springValue = useSpring(motionValue, {
    damping: 30,
    stiffness: 100,
  })
  const isInView = useInView(ref, { once: true, margin: "-50px" })

  useEffect(() => {
    if (isInView) {
      setTimeout(() => {
        motionValue.set(value)
      }, delay)
    }
  }, [motionValue, isInView, value, delay])

  useEffect(() => {
    if (ref.current && ref.current.textContent === "") {
      ref.current.textContent = formatter(motionValue.get())
    }
    return springValue.on("change", (latest) => {
      if (ref.current) {
        ref.current.textContent = formatter(latest)
      }
    })
  }, [springValue, formatter, motionValue])

  return <span ref={ref} className={cn("inline-block", className)} />
}
