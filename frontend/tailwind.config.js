/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        panel: '#111827',
        border: '#1f2937',
        soft: '#94a3b8'
      }
    },
  },
  plugins: [],
}
