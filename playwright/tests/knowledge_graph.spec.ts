import { expect, test } from '@playwright/test';

const headingText = 'SensibLaw Operations Console';
const fixtureQuery = '/?graph_fixture=knowledge_graph_docs.json';

test.describe('Knowledge Graph fixture mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(fixtureQuery);
    await expect(page.getByRole('heading', { name: headingText })).toBeVisible({ timeout: 10_000 });
    await page.getByRole('tab', { name: 'Knowledge Graph' }).click();
    await expect(page.getByText(/Graph fixture configured/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/Fixture mode \(read-only, structural only\)/)).toBeVisible({
      timeout: 10_000,
    });
  });

  test('renders structural fixture and stays read-only', async ({ page }) => {
    await expect(page.getByText('Nodes').first()).toBeVisible();
    await expect(page.getByText('Edges').first()).toBeVisible();
    await expect(page.getByLabel('Ingested graph store')).toHaveCount(0); // read-only fixture mode
  });

  test('omits inferred semantics in fixture view', async ({ page }) => {
    await expect(page.getByText(/applies/i)).toHaveCount(0);
    await expect(page.getByText(/violates/i)).toHaveCount(0);
  });
});
