/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        esg: {
          dark: '#0B0F17',
          darker: '#070A0F',
          green: '#10B981',
          accent: '#3B82F6',
          border: '#1F2937',
        }
      }
    },
  },
  plugins: [],
}
