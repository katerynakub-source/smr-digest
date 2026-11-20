// Extends app.json. EXPO_BASE_URL lets the web build live under a sub-path,
// e.g. https://<user>.github.io/smr-digest/ (set by the GitHub Actions workflow).
module.exports = ({ config }) => ({
  ...config,
  web: { ...config.web, output: 'single' },
  experiments: {
    ...config.experiments,
    ...(process.env.EXPO_BASE_URL ? { baseUrl: process.env.EXPO_BASE_URL } : {}),
  },
});
