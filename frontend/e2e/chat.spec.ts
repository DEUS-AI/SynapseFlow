import { test, expect } from '@playwright/test';

test.describe('Patient Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/chat/patient:demo');
  });

  test('should display chat interface with patient context', async ({ page }) => {
    // Check main chat interface
    await expect(page.getByRole('heading', { name: 'Medical Assistant' })).toBeVisible();

    // Check connection status
    await expect(page.getByText(/Connected|Disconnected/)).toBeVisible();

    // Check patient context sidebar
    await expect(page.getByText('Patient Context')).toBeVisible();

    // Check message input
    await expect(page.getByPlaceholder('Ask a medical question...')).toBeVisible();
  });

  test('should show WebSocket connection status', async ({ page }) => {
    // Wait for WebSocket connection
    await page.waitForTimeout(2000);

    // Check for connected indicator (green dot or "Connected" text)
    const connectionStatus = page.locator('.bg-green-500, .text-green-500').or(page.getByText('Connected'));
    await expect(connectionStatus.first()).toBeVisible({ timeout: 10000 });
  });

  test('should allow sending messages', async ({ page }) => {
    const messageInput = page.getByPlaceholder('Ask a medical question...');
    const testMessage = 'What medications am I taking?';

    // Type and send message
    await messageInput.fill(testMessage);
    await messageInput.press('Enter');

    // Check message appears in chat
    await expect(page.getByText(testMessage)).toBeVisible();
  });

  test('should display patient context information', async ({ page }) => {
    // Wait for patient context to load
    await page.waitForTimeout(2000);

    // Check that patient context section exists
    const contextSection = page.locator('text=Patient Context').locator('..');
    await expect(contextSection).toBeVisible();
  });

  test('should have functional message input', async ({ page }) => {
    const messageInput = page.getByPlaceholder('Ask a medical question...');

    // Input should be enabled
    await expect(messageInput).toBeEnabled();

    // Should accept text
    await messageInput.fill('Test message');
    await expect(messageInput).toHaveValue('Test message');
  });
});
