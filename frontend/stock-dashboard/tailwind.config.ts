import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        paper: "#f7f8f5",
        line: "#d9ded7",
        risk: "#c2410c",
        watch: "#b45309",
        trust: "#166534",
        data: "#0369a1"
      },
      boxShadow: {
        panel: "0 12px 32px rgba(23, 32, 38, 0.08)"
      }
    }
  },
  plugins: []
} satisfies Config;
