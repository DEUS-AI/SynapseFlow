/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'hsl(222 47% 11%)',
        foreground: 'hsl(210 40% 98%)',
        card: 'hsl(222 47% 14%)',
        'card-foreground': 'hsl(210 40% 98%)',
        border: 'hsl(217 33% 25%)',
        input: 'hsl(217 33% 25%)',
        primary: 'hsl(210 100% 50%)',
        'primary-foreground': 'hsl(210 40% 98%)',
        secondary: 'hsl(217 33% 20%)',
        'secondary-foreground': 'hsl(210 40% 98%)',
        muted: 'hsl(217 33% 20%)',
        'muted-foreground': 'hsl(215 20% 65%)',
        accent: 'hsl(217 33% 25%)',
        'accent-foreground': 'hsl(210 40% 98%)',
        destructive: 'hsl(0 62% 50%)',
        'destructive-foreground': 'hsl(210 40% 98%)',
        success: 'hsl(142 76% 36%)',
        warning: 'hsl(38 92% 50%)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
