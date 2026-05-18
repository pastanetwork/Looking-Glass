/** Configuration Tailwind,
 *  police Outfit (libre, OFL).
 *  @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static_dev/assets/js/**/*.js",
  ],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Outfit", "system-ui", "sans-serif"],
        mono: ["CascadiaCode", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        dark: "var(--c-dark)",
        "dark-soft": "var(--c-dark-soft)",
        "dark-band": "var(--c-dark-band)",
        page: "var(--c-page)",
        "gray-section": "var(--c-gray-section)",
        "gray-card": "var(--c-gray-card)",
        "border-l": "var(--c-border)",
        "text-primary": "var(--c-text-primary)",
        "text-secondary": "var(--c-text-secondary)",
        "text-muted": "var(--c-text-muted)",
        gold: "#f0a030",
        "gold-hover": "#e89020",
        "gold-light": "var(--c-gold-light)",
        orange: "#e87530",
        cream: "var(--c-cream)",
        "cream-muted": "var(--c-cream-muted)",
      },
      borderRadius: {
        xl: "1rem",
      },
    },
  },
  plugins: [],
};
