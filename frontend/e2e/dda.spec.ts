import { test, expect } from '@playwright/test';

test.describe('DDA Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dda');
  });

  test('should display DDA management interface', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'DDA Management' })).toBeVisible();
  });

  test('should display upload component', async ({ page }) => {
    // Check for upload section
    await expect(page.getByText('Upload DDA Specification')).toBeVisible();

    // Check for file input
    await expect(page.getByText('Choose DDA file')).toBeVisible();

    // Check for upload button
    await expect(page.getByRole('button', { name: /Upload and Process/i })).toBeVisible();
  });

  test('should display data catalog browser', async ({ page }) => {
    // Check for catalog section
    await expect(page.getByText('Data Catalog Browser')).toBeVisible();

    // Check for search input
    await expect(page.getByPlaceholder('Search by name or description...')).toBeVisible();

    // Check for filter buttons
    await expect(page.getByRole('button', { name: /All/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Catalogs/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Schemas/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Tables/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Columns/i })).toBeVisible();
  });

  test('should have functional catalog search', async ({ page }) => {
    const searchInput = page.getByPlaceholder('Search by name or description...');

    await searchInput.fill('test');
    await expect(searchInput).toHaveValue('test');
  });

  test('should display quick links', async ({ page }) => {
    // Check for metadata viewer link
    await expect(page.getByRole('link', { name: /Metadata Viewer/i })).toBeVisible();

    // Check for knowledge graph link
    await expect(page.getByRole('link', { name: /Knowledge Graph/i })).toBeVisible();
  });

  test('should navigate to metadata viewer', async ({ page }) => {
    await page.getByRole('link', { name: /Metadata Viewer/i }).click();

    await expect(page).toHaveURL('/dda/metadata');
    await expect(page.getByRole('heading', { name: 'Metadata Viewer' })).toBeVisible();
  });

  test('upload button should be disabled without file', async ({ page }) => {
    const uploadButton = page.getByRole('button', { name: /Upload and Process/i });
    await expect(uploadButton).toBeDisabled();
  });
});

test.describe('Metadata Viewer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dda/metadata');
  });

  test('should display metadata viewer', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Metadata Viewer' })).toBeVisible();
  });

  test('should display three-panel layout', async ({ page }) => {
    // Check for all three sections
    await expect(page.getByText('Catalogs')).toBeVisible();
    await expect(page.getByText('Schemas')).toBeVisible();
    await expect(page.getByText('Tables')).toBeVisible();
  });

  test('should have back button', async ({ page }) => {
    const backButton = page.getByRole('link', { name: /Back to DDA Management/i });
    await expect(backButton).toBeVisible();

    await backButton.click();
    await expect(page).toHaveURL('/dda');
  });

  test('should show appropriate messages when no data', async ({ page }) => {
    // Wait for data to load or timeout
    await page.waitForTimeout(2000);

    // Should show either data or "no data" messages
    const catalogs = page.getByText(/No catalogs found|Loading catalogs/);
    await expect(catalogs.first()).toBeVisible();
  });
});
