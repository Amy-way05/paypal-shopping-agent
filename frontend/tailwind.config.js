/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0A1F44',          // deep navy: text + hero surface
        navy: '#003087',         // PayPal navy
        pay: '#0070E0',          // PayPal blue: actions
        'pay-dark': '#005EC4',
        'pay-soft': '#E6F0FD',
        save: '#12805C',         // money kept: text on light
        'save-soft': '#E4F4EC',
        'save-bright': '#2BD47D', // money kept: on navy
        paper: '#F3F5F9',
        line: '#DCE2EC',
        muted: '#5B6B85',
        warn: '#9A5B06',          // no longer used for text: it read as brown
        amber: '#F5A524',         // small signals only (bars, dots)
        'warn-soft': '#FFF3D6',
        danger: '#B3261E',
        'danger-soft': '#FCE8E6',
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['Figtree', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        pop: {
          '0%': { opacity: '0', transform: 'translateY(12px) scale(.9)' },
          '15%': { opacity: '1', transform: 'translateY(0) scale(1.04)' },
          '25%': { transform: 'scale(1)' },
          '85%': { opacity: '1', transform: 'translateY(-6px) scale(1)' },
          '100%': { opacity: '0', transform: 'translateY(-18px) scale(.98)' },
        },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        slidein: { from: { transform: 'translateX(100%)' }, to: { transform: 'translateX(0)' } },
        rise: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
      },
      animation: {
        pop: 'pop 2.4s ease-out forwards',
        slidein: 'slidein .22s ease-out',
        rise: 'rise .18s ease-out',
      },
    },
  },
  plugins: [],
}
