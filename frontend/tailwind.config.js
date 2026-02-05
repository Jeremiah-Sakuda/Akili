/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: '#0066cc',
        'background-light': '#f5f7f8',
        'background-dark': '#0f1923',
      },
      fontFamily: {
        display: ['Inter', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        soft: 'rgba(0,0,0,0.05) 0px 0px 20px',
      },
    },
  },
  plugins: [],
};
