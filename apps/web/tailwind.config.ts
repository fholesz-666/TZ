import type { Config } from "tailwindcss";
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14181d",
        muted: "#5b6573",
        line: "#e3e7ec",
        accent: "#1f6feb",
        warn: "#b7791f",
        bad: "#c0392b",
        good: "#1e7e50",
      },
    },
  },
} satisfies Config;
