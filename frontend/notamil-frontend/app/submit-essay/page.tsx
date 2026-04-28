// app/submit-essay/page.tsx
"use client";
import { redirect } from "next/navigation";

export default function SubmitEssayPage() {
  // Redireciona para a tela de seleção
  redirect("/submit-essay/select");
  return null;
}