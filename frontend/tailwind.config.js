/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0f172a",
        card: "#1e293b",
        accent: "#FF9900",
      },
      boxShadow: { panel: "0 12px 30px rgba(2, 6, 23, 0.3)" },
    },
  },
  plugins: [],
};