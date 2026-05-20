/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        serif: ["Fraunces", "Georgia", "serif"],
        sans: ["Geist", "Inter", "system-ui", "-apple-system", "sans-serif"]
      },
      colors: {
        // legacy aliases (redirected to new palette via CSS vars)
        ink: "var(--ink)",
        line: "var(--hairline)",
        paper: "var(--bg)",
        brand: "var(--accent)",
        accent: "var(--accent)",
        ocean: "var(--ink)",
        // new thor palette
        thor: {
          bg: "var(--bg)",
          elev: "var(--bg-elev)",
          sunk: "var(--bg-sunk)",
          ink: "var(--ink)",
          "ink-soft": "var(--ink-soft)",
          "ink-mute": "var(--ink-mute)",
          hairline: "var(--hairline)",
          "hairline-strong": "var(--hairline-strong)",
          accent: "var(--accent)",
          "accent-hover": "var(--accent-hover)",
          "accent-soft": "var(--accent-soft)",
          amber: "var(--amber)",
          ok: "var(--ok)",
          "ok-soft": "var(--ok-soft)",
          warn: "var(--warn)",
          "warn-soft": "var(--warn-soft)",
          info: "var(--info)",
          "info-soft": "var(--info-soft)",
          danger: "var(--danger)",
          "danger-soft": "var(--danger-soft)",
          "bubble-client": "var(--bubble-client)",
          "bubble-agent": "var(--bubble-agent)"
        }
      },
      letterSpacing: {
        smallcaps: "0.12em",
        editorial: "-0.015em"
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      },
      animation: {
        rise: "rise .7s ease forwards"
      }
    }
  },
  plugins: []
};
