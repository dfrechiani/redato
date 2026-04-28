"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";
import { LoadingSpinner } from "./LoadingSpinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-ink text-white hover:bg-ink-800 active:bg-ink-900 disabled:bg-ink-200 disabled:text-ink-400",
  secondary:
    "bg-lime text-lime-ink hover:brightness-95 active:brightness-90 disabled:bg-ink-200 disabled:text-ink-400",
  ghost:
    "bg-transparent text-ink hover:bg-ink-100 active:bg-ink-200 disabled:text-ink-400",
  danger:
    "bg-danger text-white hover:brightness-95 disabled:bg-ink-200 disabled:text-ink-400",
};

const sizeClasses: Record<Size, string> = {
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    fullWidth = false,
    disabled,
    className,
    children,
    type = "button",
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium",
        "transition-colors disabled:cursor-not-allowed",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime",
        "focus-visible:ring-offset-2 focus-visible:ring-offset-white",
        variantClasses[variant],
        sizeClasses[size],
        fullWidth && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && <LoadingSpinner size={16} />}
      {children}
    </button>
  );
});
