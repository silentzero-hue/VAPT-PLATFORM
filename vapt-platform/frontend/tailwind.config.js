/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0b1020",
          panel: "#11182d",
          soft: "#0f1530",
          deep: "#070b1a",
        },
        border: {
          DEFAULT: "#1d2640",
          soft: "#222b4a",
          glass: "rgba(255,255,255,0.08)",
          "glass-strong": "rgba(255,255,255,0.14)",
        },
        fg: {
          DEFAULT: "#e6e9f5",
          muted: "#8a92b2",
          subtle: "#5e6885",
        },
        accent: {
          DEFAULT: "#5b8def",
          strong: "#7aa1ff",
        },
        // severity scale
        sev: {
          critical: "#ff4d6d",
          high: "#ff8c42",
          medium: "#ffd166",
          low: "#3ddc97",
          info: "#7aa1ff",
        },
      },
      boxShadow: {
        panel: "0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px rgba(0,0,0,0.32)",
        glass: "0 4px 24px rgba(0,0,0,0.25)",
        "glass-strong": "0 8px 32px rgba(0,0,0,0.35)",
        "accent-glow": "0 0 0 1px rgba(91, 141, 239, 0.4)",
        "inner-border": "inset 0 0 0 1px rgba(255,255,255,0.06)",
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
