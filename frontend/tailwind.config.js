/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        blush: "#FFF7FA",
        line: "#F7D9E6",
        ink: "#1F1A1D",
        muted: "#8C7B84",
        plus: "#0E9F6E",
        minus: "#D9435E",
        rose: {
          50: "#FFF1F6",
          100: "#FDE8F0",
          200: "#FBCFE1",
          300: "#F7A8C7",
          400: "#F075A3",
          500: "#E8457F",
          600: "#D63570",
          700: "#B0245A",
          800: "#8C1D49",
        },
      },
      fontFamily: {
        sans: ["Manrope", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(232,69,127,0.06), 0 10px 30px -12px rgba(232,69,127,0.22)",
        pop: "0 12px 32px -8px rgba(232,69,127,0.45)",
      },
      keyframes: {
        rise: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: { rise: "rise .25s ease-out both" },
    },
  },
  plugins: [],
};
