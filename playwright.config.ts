import { defineConfig, devices } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const PORT = process.env.PLAYWRIGHT_PORT ?? '8501';
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${PORT}`;
const streamlitFromVenv = path.join(__dirname, 'venv', 'bin', 'streamlit');
const streamlitExecutable = fs.existsSync(streamlitFromVenv)
  ? streamlitFromVenv
  : 'streamlit';
const graphFixturePath = path.resolve(
  __dirname,
  'tests',
  'fixtures',
  'ui',
  'knowledge_graph_docs.json',
);
const uiFixtureDir = path.resolve(__dirname, 'tests', 'fixtures', 'ui');

process.env.SENSIBLAW_GRAPH_FIXTURE = graphFixturePath;
process.env.SENSIBLAW_FORCE_GRAPH_FIXTURE = graphFixturePath;
process.env.SENSIBLAW_UI_FIXTURE_DIR = uiFixtureDir;

export default defineConfig({
  testDir: './playwright/tests',
  timeout: 120_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: true,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: !process.env.PWDEBUG,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `bash -c \"SENSIBLAW_GRAPH_FIXTURE=${graphFixturePath} SENSIBLAW_FORCE_GRAPH_FIXTURE=${graphFixturePath} ${streamlitExecutable} run sensiblaw_streamlit/app.py --server.port=${PORT} --server.headless true --browser.gatherUsageStats false --server.fileWatcherType none\"`,
    url: baseURL,
    timeout: 120_000,
    reuseExistingServer: false,
    cwd: path.join(__dirname),
    env: {
      PYTHONPATH: path.join(__dirname),
      STREAMLIT_SERVER_HEADLESS: 'true',
      SENSIBLAW_GRAPH_FIXTURE: graphFixturePath,
      SENSIBLAW_FORCE_GRAPH_FIXTURE: graphFixturePath,
      SENSIBLAW_UI_FIXTURE_DIR: uiFixtureDir,
    },
  },
});
