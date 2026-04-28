"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/hooks/useAuth";
import * as authClient from "@/lib/auth-client";
import { cn } from "@/lib/cn";
import { Logo } from "@/components/ui/Logo";

export function Header() {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const clear = useAuth((s) => s.clear);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onLogout() {
    setLoading(true);
    try {
      await authClient.logout();
      clear();
      toast.success("Sessão encerrada.");
      router.push("/login");
    } catch {
      // Mesmo com erro, derruba sessão local
      clear();
      router.push("/login");
    } finally {
      setLoading(false);
      setOpen(false);
    }
  }

  if (!user) return null;

  const primeiro = user.nome.split(" ")[0] || user.nome;

  return (
    <header className="border-b border-border bg-white sticky top-0 z-30">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <Link href="/" aria-label="Início">
          <Logo />
        </Link>

        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className={cn(
              "flex items-center gap-2 px-3 h-9 rounded-lg text-sm",
              "hover:bg-ink-100 transition-colors",
            )}
            aria-haspopup="menu"
            aria-expanded={open}
          >
            <span
              className="h-7 w-7 rounded-full bg-ink text-white text-xs font-semibold flex items-center justify-center"
              aria-hidden="true"
            >
              {primeiro.charAt(0).toUpperCase()}
            </span>
            <span className="hidden sm:inline">{primeiro}</span>
            <span className="text-ink-400" aria-hidden="true">▾</span>
          </button>

          {open && (
            <div
              role="menu"
              className="absolute right-0 top-11 w-64 bg-white border border-border rounded-xl shadow-card p-1 z-40"
            >
              <div className="px-3 py-2.5 border-b border-border">
                <p className="text-sm font-semibold leading-tight">{user.nome}</p>
                <p className="text-xs text-ink-400 truncate">{user.email}</p>
                <p className="text-xs text-ink-400 mt-0.5 capitalize">
                  {user.papel} · {user.escola_nome}
                </p>
              </div>
              {user.papel === "coordenador" && (
                <Link
                  href="/escola/dashboard"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className={cn(
                    "block w-full text-left px-3 py-2 text-sm rounded-lg",
                    "hover:bg-ink-100 transition-colors",
                  )}
                >
                  Dashboard escola
                </Link>
              )}
              <Link
                href="/perfil"
                role="menuitem"
                onClick={() => setOpen(false)}
                className={cn(
                  "block w-full text-left px-3 py-2 text-sm rounded-lg",
                  "hover:bg-ink-100 transition-colors",
                )}
              >
                Perfil
              </Link>
              <button
                type="button"
                role="menuitem"
                onClick={onLogout}
                disabled={loading}
                className={cn(
                  "w-full text-left px-3 py-2 text-sm rounded-lg",
                  "hover:bg-ink-100 transition-colors",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                )}
              >
                {loading ? "Saindo…" : "Sair"}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
