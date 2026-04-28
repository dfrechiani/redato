"use client";

import { forwardRef, useState, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/cn";
import { Input } from "./Input";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  invalid?: boolean;
}

export const PasswordInput = forwardRef<HTMLInputElement, Props>(
  function PasswordInput({ className, ...rest }, ref) {
    const [shown, setShown] = useState(false);
    return (
      <div className="relative">
        <Input
          ref={ref}
          type={shown ? "text" : "password"}
          className={cn("pr-12", className)}
          autoComplete="current-password"
          {...rest}
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          className={cn(
            "absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1",
            "text-xs font-mono uppercase tracking-wider rounded",
            "text-ink-400 hover:text-ink-800 hover:bg-ink-100 transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime",
          )}
          aria-label={shown ? "Ocultar senha" : "Mostrar senha"}
          tabIndex={-1}
        >
          {shown ? "ocultar" : "mostrar"}
        </button>
      </div>
    );
  },
);
