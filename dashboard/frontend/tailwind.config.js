/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        graphite: '#111315',
        ink: '#0D1418',
        ivory: '#F7F3EA',
        stone: '#D8D0C2',
        champagne: '#B89B63',
        softgraph: '#2B2F32',
        taupe: '#7A746A',
        olive: '#4E5A50',
        bluegray: '#52616B',
        clay: '#A56C53',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        heading: ['Geist', 'Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
