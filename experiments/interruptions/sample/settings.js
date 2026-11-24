// ABOUTME: Settings page: loads settings from localStorage into the form and saves them back.
// ABOUTME: Settings are a plain object {theme, fontSize} stored under the "settings" key.
const DEFAULTS = { theme: "light", fontSize: 16 };

function loadSettings() {
  const stored = localStorage.getItem("settings");
  return stored ? { ...DEFAULTS, ...JSON.parse(stored) } : { ...DEFAULTS };
}

const form = document.getElementById("settings-form");
const settings = loadSettings();
form.theme.value = settings.theme;
form.fontSize.value = settings.fontSize;

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const saved = { theme: form.theme.value, fontSize: Number(form.fontSize.value) };
  localStorage.setItem("settings", JSON.stringify(saved));
  document.getElementById("status").textContent = "Saved";
});
