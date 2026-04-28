"use client";

import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { className, invalid = false, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        "block w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm",
        "placeholder:text-ink-400 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime",
        "disabled:bg-muted disabled:text-ink-400 disabled:cursor-not-allowed",
        invalid
          ? "border-danger focus-visible:ring-danger"
          : "border-border focus-visible:border-ink",
        className,
      )}
      {...rest}
    />
  );
});
