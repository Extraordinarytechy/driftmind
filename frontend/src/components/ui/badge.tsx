import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", {
  variants: {
    variant: {
      default: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
      warning: "border-orange-400/30 bg-orange-400/10 text-orange-300",
      destructive: "border-red-500/30 bg-red-500/10 text-red-300",
      secondary: "border-slate-600 bg-slate-700/70 text-slate-300",
    },
  },
  defaultVariants: { variant: "default" },
});
interface BadgeProps extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}
export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}