import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "sans-serif"],
      },
      colors: {
        background: "#0a0a0a",
        surface: {
          DEFAULT: "#111111",
          raised: "#161616",
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
