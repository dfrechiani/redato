import type { Metadata, Viewport } from "next";
import { DM_Serif_Display, JetBrains_Mono, Source_Sans_3 } from "next/font/google";
import { Toaster } from "sonner";

import "./globals.css";

const display = DM_Serif_Display({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-display",
  display: "swap",
});

const body = Source_Sans_3({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Redato — Portal do Professor",
  description:
    "Redato é a corretora do Projeto ATO. Portal de turmas, atividades e dashboard pedagógico.",
  applicationName: "Redato",
  authors: [{ name: "Projeto ATO" }],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0f1117",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="pt-BR"
      className={`${display.variable} ${body.variable} ${mono.variable}`}
    >
      <body className="font-body bg-white text-ink min-h-screen antialiased">
        {children}
        <Toaster
          position="top-right"
          richColors
          closeButton
          toastOptions={{
            classNames: {
              toast: "font-body",
            },
          }}
        />
      </body>
    </html>
  );
}
