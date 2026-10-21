import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Squarer, engraved-plate scale: every container follows it.
      borderRadius: {
        sm: "2px", DEFAULT: "3px", md: "4px", lg: "4px",
        xl: "6px", "2xl": "6px", "3xl": "8px", full: "9999px",
      },
      colors: {
        // Near-hueless graphite scale so every slate-* class follows the theme.
        slate: {
          50: "#F7F7F8",
          100: "#EDEDEF",
          200: "#DBDCDF",
          300: "#C0C2C7",
          400: "#A8ABB1",
          500: "#888C93",
          600: "#676A70",
          700: "#484B50",
          800: "#2D2F33",
          900: "#1E2023",
          950: "#151618",
        },
        ucn: {
          azul: "var(--ucn-azul)",
          "azul-claro": "var(--ucn-azul-claro)",
          tierra: "var(--ucn-tierra)",
          "tierra-clara": "var(--ucn-tierra-clara)",
        },
        dato: {
          favorable: "var(--dato-favorable)",
          neutro: "var(--dato-neutro)",
          adverso: "var(--dato-adverso)",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
