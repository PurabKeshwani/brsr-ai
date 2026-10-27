import { cn } from "@/lib/utils"

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "notable" | "worth_reviewing";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "bg-muted text-muted-foreground border-border",
    success: "bg-accent/10 text-accent border-accent/20",
    warning: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    danger: "bg-rose-500/10 text-rose-500 border-rose-500/20",
    info: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    notable: "bg-orange-500/10 text-orange-400 border-orange-500/20 font-bold",
    worth_reviewing: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
        variants[variant],
        className
      )}
      {...props}
    />
  )
}
