import { test, expect } from '@playwright/test';

test.describe('Home Page', () => {
  test('should display the home page with all feature cards', async ({ page }) => {
    await page.goto('/');

    // Check header
    await expect(page.getByRole('heading', { name: 'Medical Knowledge Management System' })).toBeVisible();

    // Check all 4 feature cards are present
    await expect(page.getByText('Patient Chat')).toBeVisible();
    await expect(page.getByText('Knowledge Graph')).toBeVisible();
    await expect(page.getByText('Admin Dashboard')).toBeVisible();
    await expect(page.getByText('DDA Management')).toBeVisible();
  });

  test('should navigate to patient chat', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Patient Chat/i }).click();

    await expect(page).toHaveURL(/\/chat\//);
    await expect(page.getByRole('heading', { name: 'Medical Assistant' })).toBeVisible();
  });

  test('should navigate to knowledge graph', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Knowledge Graph/i }).click();

    await expect(page).toHaveURL('/graph');
  });

  test('should navigate to admin dashboard', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Admin Dashboard/i }).click();

    await expect(page).toHaveURL('/admin');
    await expect(page.getByRole('heading', { name: 'Admin Dashboard' })).toBeVisible();
  });

  test('should navigate to DDA management', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /DDA Management/i }).click();

    await expect(page).toHaveURL('/dda');
    await expect(page.getByRole('heading', { name: 'DDA Management' })).toBeVisible();
  });
});
