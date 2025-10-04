/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './**/templates/**/*.html', // <-- Универсальный путь для всех приложений
    './static/js/**/*.js'      // <-- Добавлено сканирование JS файлов на всякий случай
  ],
  theme: {
    extend: {
      backgroundImage: {
        'doodle-pattern': "url('/static/img/bg.jpg')",
      }
    },
  },
  plugins: [],
}