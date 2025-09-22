/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
      './templates/**/*.html',
      './core/templates/**/*.html',
  ],
  theme: {
    extend: {
      // --- ДОБАВЬ ЭТОТ БЛОК ---
      backgroundImage: {
        'doodle-pattern': "url('/static/img/bg.jpg')",
      }
    },
  },
  plugins: [],
}