/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        // white → warm card/surface color (#EEE6DA)
        // bg-white (nav, cards, footer, dropdowns) = warm off-white card surface
        // text-white on bg-green-600 (#724330): #EEE6DA gives 5.9:1 contrast ✓ AA
        // EXCEPTION: bg-amber-600 text-white — fixed to text-gray-900 in order_detail.html
        white: '#EEE6DA',

        // green → espresso-mahogany scale
        // green-600 = #724330 (primary buttons, links, accents)
        // green-700 = #5A3424 (hover state)
        green: {
          50:  '#F5ECD8',
          100: '#EDDBBC',
          200: '#D9BF98',
          300: '#C49A6A',
          400: '#B07335',
          500: '#9B6530',
          600: '#724330',
          700: '#5A3424',
          800: '#3E2010',
          900: '#28140A',
        },

        // gray → warm stone scale
        // gray-50 (#E6DCD0) = page background  (body bg-gray-50)
        // gray-100 (#D9CEC2) = card borders — darker than both bg & card for a visible edge
        // WCAG AA floor on #E6DCD0 bg = gray-500 (4.9:1 ✓); gray-400 = non-text only
        gray: {
          50:  '#E6DCD0',
          100: '#D9CEC2',
          200: '#C5B4A0',
          300: '#A99280',
          400: '#8C7862',
          500: '#6A5A48',
          600: '#5C4E3E',
          700: '#4A3D30',
          800: '#2E2418',
          900: '#1A1410',
        },
      },
    },
  },
  plugins: [],
}
