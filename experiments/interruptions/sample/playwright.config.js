// ABOUTME: Playwright config: serves the static site with Python's http.server on port 8123.
// ABOUTME: Tests run headless in Chromium only.
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests",
  use: { baseURL: "http://127.0.0.1:8123", browserName: "chromium" },
  webServer: { command: "python3 -m http.server 8123", url: "http://127.0.0.1:8123", reuseExistingServer: true },
});
