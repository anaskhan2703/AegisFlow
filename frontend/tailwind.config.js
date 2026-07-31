/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Dark cybersecurity theme palette — reused across Threat Intel,
        // Alert, and Identity Risk pages built in later phases.
        "soc-bg": "#0b0e14",
        "soc-panel": "#131720",
        "soc-border": "#232838",
        "soc-critical": "#ef4444",
        "soc-high": "#f97316",
        "soc-medium": "#eab308",
        "soc-low": "#3b82f6",
        "soc-safe": "#22c55e",
        "soc-accent": "#06b6d4",
      },
    },
  },
  plugins: [],
};
