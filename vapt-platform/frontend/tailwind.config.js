/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // macOS Finder light-theme palette
        paper: "#fbfaf8",
        "paper-soft": "#f5f3ed",
        "paper-strong": "#ffffff",
        "paper-deep": "#ede9de",
        ink: "#26251f",
        "ink-muted": "#6b6a63",
        "ink-subtle": "#9c9a92",
        hairline: "rgba(0,0,0,0.10)",
        "hairline-strong": "rgba(0,0,0,0.18)",
        "finder-blue": "#0a84ff",
        "finder-blue-soft": "rgba(10,132,255,0.16)",
        "folder-from": "#6fb1fc",
        "folder-to": "#2e7cf6",
        // Backwards-compatible aliases (used by older code)
        bg: {
          DEFAULT: "#fbfaf8",
          panel: "#ffffff",
          soft: "#f5f3ed",
          deep: "#ede9de",
        },
        border: {
          DEFAULT: "rgba(0,0,0,0.10)",
          soft: "rgba(0,0,0,0.06)",
          glass: "rgba(255,255,255,0.7)",
          "glass-strong": "rgba(255,255,255,0.9)",
        },
        fg: {
          DEFAULT: "#26251f",
          muted: "#6b6a63",
          subtle: "#9c9a92",
        },
        accent: {
          DEFAULT: "#0a84ff",
          strong: "#0a84ff",
        },
        // Severity scale (Finder-aligned, slightly muted for light bg)
        sev: {
          critical: "#ff3b30",
          high: "#ff9500",
          medium: "#ffcc00",
          low: "#34c759",
          info: "#5e5ce6",
        },
      },
      boxShadow: {
        panel: "0 1px 0 rgba(0,0,0,0.02) inset, 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
        glass: "0 4px 24px rgba(0,0,0,0.08)",
        "glass-strong": "0 8px 32px rgba(0,0,0,0.12)",
        "accent-glow": "0 0 0 1px rgba(10,132,255,0.4)",
        "inner-border": "inset 0 0 0 1px rgba(0,0,0,0.05)",
        card: "0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06)",
      },
      backdropBlur: {
        xs: "2px",
        glass: "20px",
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      transitionDuration: {
        "200": "200ms",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "slide-down": {
          "0%": { transform: "translateY(-100%)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "slide-in": {
          "0%": { transform: "translateX(-100%)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        "slide-down": "slide-down 200ms ease-out",
        "slide-in": "slide-in 200ms ease-out",
        "fade-in": "fade-in 200ms ease-out",
      },
    },
  },
  plugins: [],
};
