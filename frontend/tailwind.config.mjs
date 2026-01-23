/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(0 0% 100%)', // white
        foreground: 'hsl(222.2 84% 4.9%)', // dark blue-gray
      },
    },
  },
  plugins: [],
}
