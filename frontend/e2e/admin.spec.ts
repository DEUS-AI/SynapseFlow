import { test, expect } from '@playwright/test';

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin');
  });

  test('should display the admin dashboard', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Admin Dashboard' })).toBeVisible();
  });

  test('should display system metrics', async ({ page }) => {
    // Wait for metrics to load
    await page.waitForTimeout(2000);

    // Check for metric labels
    await expect(page.getByText('System Metrics')).toBeVisible();
    await expect(page.getByText(/Total Queries|Active Sessions|Total Patients/)).toBeVisible();
  });

  test('should display agent monitor', async ({ page }) => {
    // Wait for agents to load
    await page.waitForTimeout(2000);

    // Check agent monitor section
    await expect(page.getByText('Agent Status')).toBeVisible();
  });

  test('should navigate to patient management', async ({ page }) => {
    await page.getByRole('link', { name: /Manage Patients/i }).click();

    await expect(page).toHaveURL('/admin/patients');
    await expect(page.getByRole('heading', { name: 'Patient Management' })).toBeVisible();
  });

  test('should display Neo4j statistics', async ({ page }) => {
    // Wait for data to load
    await page.waitForTimeout(2000);

    // Check for Neo4j section
    await expect(page.getByText(/Neo4j Graph|Nodes|Relationships/)).toBeVisible();
  });
});

test.describe('Patient Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin/patients');
  });

  test('should display patient management interface', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Patient Management' })).toBeVisible();

    // Check for search box
    await expect(page.getByPlaceholder('Search patients...')).toBeVisible();

    // Check for patient table
    await expect(page.getByRole('table')).toBeVisible();
  });

  test('should have functional search', async ({ page }) => {
    const searchInput = page.getByPlaceholder('Search patients...');

    await searchInput.fill('demo');
    await expect(searchInput).toHaveValue('demo');
  });

  test('should display table headers', async ({ page }) => {
    // Check for table headers
    await expect(page.getByRole('columnheader', { name: /Patient ID/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /Created/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /Actions/i })).toBeVisible();
  });
});
