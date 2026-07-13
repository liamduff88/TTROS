const tokenColor = (name) =>
  `color-mix(in srgb, var(${name}) calc(<alpha-value> * 100%), transparent)`

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        graphite: tokenColor('--surface-1'),
        ink: tokenColor('--surface-0'),
        well: tokenColor('--surface-2'),
        ivory: tokenColor('--text'),
        stone: tokenColor('--text'),
        champagne: tokenColor('--wb-hermes-queued'),
        softgraph: tokenColor('--hairline'),
        taupe: tokenColor('--text-dim'),
        olive: tokenColor('--lane-marketing'),
        bluegray: tokenColor('--wb-codex-queued'),
        clay: tokenColor('--wb-claude-working'),
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
        heading: ['system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
