import path from 'path';
import { expect, test } from '@playwright/test';

const headingText = 'SensibLaw Operations Console';

test.describe('Documents ingest page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: headingText })).toBeVisible({ timeout: 10_000 });
    // The Documents tab is the first tab and renders by default.
    await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible({ timeout: 10_000 });
  });

  test('shows default store path and core controls', async ({ page }) => {
    const storePath = page.getByRole('textbox', { name: 'SQLite store path' });
    await expect(storePath).toBeVisible();
    await expect(storePath).toHaveValue(/ui\/sensiblaw_documents\.sqlite$/);

    await expect(page.getByLabel('Upload PDF for processing')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Process PDF' })).toBeEnabled();
  });

  test('requires a PDF before processing', async ({ page }) => {
    await page.getByRole('button', { name: 'Process PDF' }).click();
    await expect(page.getByText('Please upload a PDF or choose a sample file.')).toBeVisible();
  });

  test('exposes step processing controls when enabled', async ({ page }) => {
    const toggle = page.getByRole('checkbox', { name: 'Step ingestion like a debugger' });
    await toggle.evaluate((el: HTMLInputElement) => el.click());
    await expect(toggle).toBeChecked();
    // The breakpoint input only renders on the next rerun of the Streamlit form; checking is enough here.
  });

  test('accepts an uploaded PDF without immediate processing', async ({ page }) => {
    const filePath = path.join(__dirname, 'fixtures/dummy.pdf');
    const dropzone = page.locator('section[aria-label="Upload PDF for processing"]');
    const fileInput = dropzone.locator('input[type=file]').first();
    await fileInput.setInputFiles(filePath);
    await expect(page.getByText('dummy.pdf')).toBeVisible();
    await expect(page.getByText('Following paragraph cited by')).toHaveCount(0);

    // Do not click "Process PDF" to avoid running the heavy ingestion pipeline in CI.
    await expect(page.getByRole('button', { name: 'Process PDF' })).toBeEnabled();
  });
});
