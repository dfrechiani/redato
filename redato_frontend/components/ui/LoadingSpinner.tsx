"use client";

import { cn } from "@/lib/cn";

interface Props {
  size?: number;
  className?: string;
  label?: string;
}

export function LoadingSpinner({ size = 20, className, label }: Props) {
  return (
    <span
      role={label ? "status" : undefined}
      aria-label={label}
      className={cn("inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="animate-spin"
        width={size}
        height={size}
        aria-hidden="true"
      >
        <circle
          cx="12"
          cy="12"
          r="9"
          stroke="currentColor"
          strokeWidth="2.5"
          opacity="0.2"
        />
        <path
          d="M21 12a9 9 0 0 1-9 9"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}
