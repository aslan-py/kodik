import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('https://kad.arbitr.ru/');
  await page.getByRole('textbox', { name: 'название, ИНН или ОГРН' }).click();
  await page.getByRole('textbox', { name: 'название, ИНН или ОГРН' }).fill('9718266074');
  await page.locator('i').nth(4).click();
  await page.locator('span').filter({ hasText: /^Любой$/ }).click();
  await page.getByRole('button', { name: 'Найти' }).click();
  await expect(page.getByRole('button', { name: 'Найти' })).toBeVisible();
  await expect(page.getByRole('button')).toContainText('Найти');
  await expect(page.getByRole('button')).toMatchAriaSnapshot(`- button "Найти"`);
});
