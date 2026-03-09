/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        brand: {
          DEFAULT: '#1e40af',
          light: '#3b82f6',
          dark: '#1e3a8a',
        },
        sidebar: {
          DEFAULT: '#0f172a',
          hover: '#1e293b',
          active: '#334155',
          border: '#334155',
          muted: '#64748b',
        },
      },
    },
  },
  plugins: [],
}
