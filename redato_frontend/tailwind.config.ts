import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "var(--redato-ink)",
          50: "#f4f5f7",
          100: "#e6e8ec",
          200: "#c2c7d1",
          400: "#6b7280",
          600: "#2f3340",
          800: "#1a1c25",
          900: "var(--redato-ink)",
        },
        lime: {
          DEFAULT: "var(--redato-lime)",
          ink: "#0f1117",
        },
        surface: "#ffffff",
        muted: "#f7f7f6",
        border: "#e6e8ec",
        danger: "#c43c3c",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 17, 23, 0.04), 0 4px 12px rgba(15, 17, 23, 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
