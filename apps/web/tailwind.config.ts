import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: { colors: { brand: { DEFAULT: "#3d5cf5", soft: "#e4e9ff" } } } },
  plugins: [],
} satisfies Config;
