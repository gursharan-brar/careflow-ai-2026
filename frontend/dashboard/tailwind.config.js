/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "c-navy": "var(--c-navy)",
        "c-teal": "var(--c-teal)",
        "c-teal-hover": "var(--c-teal-hover)",
        "c-bg": "var(--c-bg)",
        "c-white": "var(--c-white)",
        "c-text": "var(--c-text)",
        "c-text-muted": "var(--c-text-muted)",
        "c-border": "var(--c-border)",
        "c-urgent-bg": "var(--c-urgent-bg)",
        "c-urgent-text": "var(--c-urgent-text)",
        "c-moderate-bg": "var(--c-moderate-bg)",
        "c-moderate-text": "var(--c-moderate-text)",
        "c-routine-bg": "var(--c-routine-bg)",
        "c-routine-text": "var(--c-routine-text)",
        "c-null-bg": "var(--c-null-bg)",
        "c-null-text": "var(--c-null-text)",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
        "fade-out": {
          "0%": { opacity: "1" },
          "75%": { opacity: "1" },
          "100%": { opacity: "0" },
        },
      },
      animation: {
        shimmer: "shimmer 1.5s infinite linear",
        "fade-out": "fade-out 2s ease-in-out forwards",
      },
    },
  },
  plugins: [],
};
