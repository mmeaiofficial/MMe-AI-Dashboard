import type { Config } from "tailwindcss";

// Every color is a CSS variable (RGB channels) defined per theme in globals.css, so opacity
// modifiers like bg-well/70 keep working and no page needs its own dark: overrides.
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: { sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        brand: { DEFAULT: v("brand"), fill: v("brand-fill"), soft: v("brand-soft"), ink: v("brand-ink"), text: v("brand-text") },
        "on-brand": v("on-brand"),
        canvas: v("canvas"),
        surface: v("surface"),
        well: v("well"),
        line: v("line"),
        border: v("border"),
        ink: { DEFAULT: v("ink"), soft: v("ink-soft"), faint: v("ink-faint") },
      },
      borderRadius: { "4xl": "2rem" },
    },
  },
  plugins: [],
} satisfies Config;
