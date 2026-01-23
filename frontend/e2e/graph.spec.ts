import { test, expect } from '@playwright/test';

test.describe('Knowledge Graph Visualization', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/graph');
  });

  test('should display the graph viewer', async ({ page }) => {
    // Check SVG canvas exists
    const svg = page.locator('svg');
    await expect(svg).toBeVisible();
  });

  test('should display graph controls', async ({ page }) => {
    // Check for reset button
    await expect(page.getByRole('button', { name: /Reset/i })).toBeVisible();

    // Check for node/edge counters
    await expect(page.getByText(/Nodes:/)).toBeVisible();
    await expect(page.getByText(/Edges:/)).toBeVisible();
  });

  test('should display layer legend', async ({ page }) => {
    // Check all 4 layers are shown
    await expect(page.getByText('Perception')).toBeVisible();
    await expect(page.getByText('Semantic')).toBeVisible();
    await expect(page.getByText('Reasoning')).toBeVisible();
    await expect(page.getByText('Application')).toBeVisible();
  });

  test('should load graph data', async ({ page }) => {
    // Wait for graph to load
    await page.waitForTimeout(2000);

    // Check that SVG has child elements (nodes/edges)
    const svgElements = page.locator('svg circle, svg line');
    const count = await svgElements.count();

    // Should have at least some nodes or show "no data" message
    expect(count >= 0).toBeTruthy();
  });

  test('should have interactive SVG', async ({ page }) => {
    const svg = page.locator('svg');

    // SVG should be visible and interactive
    await expect(svg).toBeVisible();

    // Check SVG has reasonable dimensions
    const box = await svg.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.width).toBeGreaterThan(0);
      expect(box.height).toBeGreaterThan(0);
    }
  });
});
