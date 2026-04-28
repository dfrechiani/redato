"use client";

/**
 * Auth store (zustand). Mantém o user em memória pra renderização rápida.
 *
 * Source of truth real é o cookie httpOnly + endpoint /api/auth/me.
 * Esse store é só cache UI — invalidar via `refresh()` quando precisar.
 */

import { create } from "zustand";

import * as authClient from "@/lib/auth-client";
import type { AuthenticatedUser } from "@/types/api";

interface AuthState {
  user: AuthenticatedUser | null;
  loading: boolean;
  hydrated: boolean;
  setUser: (user: AuthenticatedUser | null) => void;
  refresh: () => Promise<AuthenticatedUser | null>;
  clear: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: false,
  hydrated: false,

  setUser: (user) => set({ user, hydrated: true }),

  refresh: async () => {
    set({ loading: true });
    try {
      const u = await authClient.me();
      set({ user: u, loading: false, hydrated: true });
      return u;
    } catch {
      set({ user: null, loading: false, hydrated: true });
      return null;
    }
  },

  clear: () => set({ user: null, hydrated: true }),
}));
