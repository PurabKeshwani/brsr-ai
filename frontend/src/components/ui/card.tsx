"use client"

import { cn } from "@/lib/utils"
import { HTMLMotionProps, motion } from "framer-motion"
import { forwardRef } from "react"

export const Card = forwardRef<HTMLDivElement, HTMLMotionProps<"div">>(
  ({ className, ...props }, ref) => {
    return (
      <motion.div
        ref={ref}
        className={cn(
          "glass-panel rounded-3xl p-6 transition-all duration-300",
          className
        )}
        {...props}
      />
    )
  }
)
Card.displayName = "Card"
