import { expect, test } from '@playwright/test';

const EPS_PX = 2;
const EPS_NORM = 1e-3;

const RIBBON_URL = process.env.RIBBON_DEMO_URL;

test.describe('Timeline ribbon conservation', () => {
  test.skip(!RIBBON_URL, 'RIBBON_DEMO_URL not set');

  async function sumSegmentWidthsPx(page) {
    const viewport = page.getByTestId('ribbon-viewport');
    const vpBox = await viewport.boundingBox();
    expect(vpBox).toBeTruthy();

    const segs = await page.getByTestId('segment').elementHandles();
    expect(segs.length).toBeGreaterThan(0);

    let sum = 0;
    for (const h of segs) {
      const b = await h.boundingBox();
      expect(b).toBeTruthy();
      sum += b!.width;
    }
    return { sum, viewportWidth: vpBox!.width, count: segs.length };
  }

  async function sumSegmentNorms(page) {
    const segs = await page.getByTestId('segment').elementHandles();
    let sum = 0;
    let has = 0;
    for (const h of segs) {
      const w = await h.getAttribute('data-width-norm');
      if (w != null) {
        sum += Number(w);
        has += 1;
      }
    }
    return { sum, has };
  }

  test('pixel widths conserve to viewport width', async ({ page }) => {
    await page.goto(RIBBON_URL!);
    const { sum, viewportWidth } = await sumSegmentWidthsPx(page);
    expect(Math.abs(sum - viewportWidth)).toBeLessThanOrEqual(EPS_PX);
  });

  test('normalized widths sum to 1 (if exposed)', async ({ page }) => {
    await page.goto(RIBBON_URL!);
    const { sum, has } = await sumSegmentNorms(page);
    if (has > 0) {
      expect(Math.abs(sum - 1)).toBeLessThanOrEqual(EPS_NORM);
    }
  });

  test('lens switch preserves topology/order and conserves width', async ({ page }) => {
    await page.goto(RIBBON_URL!);

    const idsBefore = await page
      .getByTestId('segment')
      .evaluateAll((els) => els.map((e) => e.getAttribute('data-seg-id')));

    await page.getByTestId('lens-switcher').click();
    await page.getByTestId('lens-item:evidence').click();

    const idsAfter = await page
      .getByTestId('segment')
      .evaluateAll((els) => els.map((e) => e.getAttribute('data-seg-id')));

    expect(idsAfter).toEqual(idsBefore);

    const { sum, viewportWidth } = await sumSegmentWidthsPx(page);
    expect(Math.abs(sum - viewportWidth)).toBeLessThanOrEqual(EPS_PX);
  });

  test('split is additive (pixel + norm)', async ({ page }) => {
    await page.goto(RIBBON_URL!);

    const before = await sumSegmentWidthsPx(page);

    await page.getByTestId('segment').first().hover();
    await page.getByRole('button', { name: 'Split' }).click();

    const after = await sumSegmentWidthsPx(page);
    expect(Math.abs(after.sum - before.sum)).toBeLessThanOrEqual(EPS_PX);
    expect(Math.abs(after.viewportWidth - before.viewportWidth)).toBeLessThanOrEqual(EPS_PX);

    const { sum, has } = await sumSegmentNorms(page);
    if (has > 0) expect(Math.abs(sum - 1)).toBeLessThanOrEqual(EPS_NORM);
  });

  test('merge is additive (pixel + norm)', async ({ page }) => {
    await page.goto(RIBBON_URL!);

    const before = await sumSegmentWidthsPx(page);

    await page.getByTestId('segment').nth(0).click();
    await page.getByTestId('segment').nth(1).click();
    await page.getByRole('button', { name: 'Merge' }).click();

    const after = await sumSegmentWidthsPx(page);
    expect(Math.abs(after.sum - before.sum)).toBeLessThanOrEqual(EPS_PX);

    const { sum, has } = await sumSegmentNorms(page);
    if (has > 0) expect(Math.abs(sum - 1)).toBeLessThanOrEqual(EPS_NORM);
  });

  test('compare overlay shows previous lens widths without changing conservation', async ({ page }) => {
    await page.goto(RIBBON_URL!);

    await page.getByTestId('lens-switcher').click();
    await page.getByTestId('lens-item:time').click();
    await page.getByTestId('lens-switcher').click();
    await page.getByTestId('lens-item:procedural').click();

    await page.getByTestId('compare-overlay-toggle').click();
    await expect(page.getByTestId('compare-overlay')).toBeVisible();

    const { sum, viewportWidth } = await sumSegmentWidthsPx(page);
    expect(Math.abs(sum - viewportWidth)).toBeLessThanOrEqual(EPS_PX);
  });
});
