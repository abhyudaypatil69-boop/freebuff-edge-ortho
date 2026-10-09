/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        stone: {
          50: "#FBFAF7",
          100: "#F5F3EC",
          200: "#EAE6DC",
          300: "#DBD5C7",
          400: "#B9B2A2",
          500: "#948C7C",
          600: "#6F6759",
          700: "#514B41",
          800: "#33302A",
          900: "#1E1C18",
          950: "#141310",
        },
        forest: {
          50: "#F0F5F2",
          100: "#DCE8E1",
          200: "#B9D1C4",
          300: "#8DB3A1",
          400: "#5E917C",
          500: "#3F735E",
          600: "#2F5B4A",
          700: "#26483C",
          800: "#1E3A30",
          900: "#172C25",
        },
        clay: {
          400: "#C98A5B",
          500: "#B4744A",
          600: "#95593A",
        },
        signal: {
          amber: "#B4791F",
          red: "#A63A2E",
          blue: "#2E5A8F",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "Geist",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(30,28,24,0.04), 0 1px 1px rgba(30,28,24,0.03)",
        raised: "0 2px 8px rgba(30,28,24,0.06), 0 1px 2px rgba(30,28,24,0.04)",
      },
      borderRadius: { card: "0.375rem" },
    },
  },
  plugins: [],
};
