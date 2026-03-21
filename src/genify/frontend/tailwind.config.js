import typography from '@tailwindcss/typography'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: { 50: '#E3F2FD', 500: '#1976D2', 600: '#1565C0', 700: '#0D47A1' },
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f9fafb',
          elevated: '#ffffff',
        },
        border: {
          subtle: '#e5e7eb',
        },
        danger: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          700: '#b91c1c',
          800: '#991b1b',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          800: '#92400e',
        },
        success: {
          50: '#f0fdf4',
          100: '#dcfce7',
          700: '#15803d',
        },
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
      },
    },
  },
  plugins: [typography],
}
