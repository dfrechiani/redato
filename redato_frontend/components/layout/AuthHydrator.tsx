"use client";

import { useEffect } from "react";

import { useAuth } from "@/hooks/useAuth";
import type { AuthenticatedUser } from "@/types/api";

interface Props {
  initialUser: AuthenticatedUser | null;
}

/**
 * Hidrata o store de auth com o user vindo do server.
 * Coloca dentro do RootLayout protegido pra que `Header` e páginas
 * tenham o user disponível imediatamente (sem flash de "logando").
 */
export function AuthHydrator({ initialUser }: Props) {
  const setUser = useAuth((s) => s.setUser);
  useEffect(() => {
    setUser(initialUser);
  }, [initialUser, setUser]);
  return null;
}
