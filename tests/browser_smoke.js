const path = require('node:path');
const { chromium } = require('playwright');

const targetUrl = process.env.TARGET_URL || 'http://127.0.0.1:8000';
const root = path.resolve(__dirname, '..');
const artifacts = path.join(root, 'reports', 'screenshots');

(async () => {
  const browser = await chromium.launch({ headless: process.env.PW_HEADLESS === 'true' });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
    const consoleErrors = [];
    page.on('console', message => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    await page.goto(targetUrl);
    await page.getByRole('heading', { name: /Measure the image/i }).waitFor();
    await page.locator('#api-status').filter({ hasText: 'API ONLINE' }).waitFor();

    await page.locator('#image-file').setInputFiles(path.join(root, 'data', 'sample', 'synthetic_cells.png'));
    await page.locator('#image-form').getByRole('button', { name: 'Run segmentation' }).click();
    await page.locator('#image-state').filter({ hasText: /objects detected/ }).waitFor();
    await page.locator('#image-visuals img').first().waitFor();
    await page.locator('#microscopy').screenshot({ path: path.join(artifacts, 'microscopy-analysis.png') });

    await page.locator('#csv-file').setInputFiles(path.join(root, 'data', 'sample', 'experiment.csv'));
    await page.locator('#csv-form').getByRole('button', { name: 'Analyze experiment' }).click();
    await page.locator('#csv-state').filter({ hasText: /60 rows/ }).waitFor();
    await page.locator('#experiment').screenshot({ path: path.join(artifacts, 'experiment-analytics.png') });

    await page.locator('#question').fill('What measurable differences were found?');
    await page.locator('#chat-form').getByRole('button', { name: 'Ask' }).click();
    await page.locator('#chat-log .message').last().filter({ hasText: 'AI INTERPRETATION' }).waitFor();

    await page.locator('#question').fill('What is the circularity measurement?');
    await page.locator('#chat-form').getByRole('button', { name: 'Ask' }).click();
    await page.locator('#chat-log .message').last().filter({ hasText: 'Mean circularity' }).waitFor();
    await page.locator('#question').fill('What does that mean?');
    await page.locator('#chat-form').getByRole('button', { name: 'Ask' }).click();
    await page.locator('#chat-log .message').last().filter({ hasText: 'Circularity approaches 1' }).waitFor();
    await page.locator('#assistant').screenshot({ path: path.join(artifacts, 'research-assistant.png') });
    await page.locator('#evaluation').screenshot({ path: path.join(artifacts, 'evaluation-methodology.png') });

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Generate report' }).click();
    const download = await downloadPromise;
    if (!download.suggestedFilename().endsWith('.html')) throw new Error('Report was not an HTML download.');
    const reportPath = path.join(root, 'reports', 'generated', 'browser-smoke-report.html');
    await download.saveAs(reportPath);

    const reportPage = await browser.newPage({ viewport: { width: 1200, height: 900 } });
    await reportPage.goto(`file:///${reportPath.replace(/\\/g, '/')}`);
    await reportPage.getByRole('heading', { name: 'CellScope AI Experiment Report' }).waitFor();
    await reportPage.screenshot({ path: path.join(artifacts, 'generated-report.png'), fullPage: true });
    await reportPage.close();

    await page.screenshot({ path: path.join(artifacts, 'dashboard-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(targetUrl);
    await page.getByRole('heading', { name: /Measure the image/i }).waitFor();
    await page.screenshot({ path: path.join(artifacts, 'dashboard-mobile.png'), fullPage: true });

    if (consoleErrors.length) throw new Error(`Browser console errors: ${consoleErrors.join(' | ')}`);
    console.log(JSON.stringify({
      title: await page.title(),
      imageWorkflow: 'passed',
      csvWorkflow: 'passed',
      chatWorkflow: 'passed',
      followUpContext: 'passed',
      reportDownload: 'passed',
      screenshots: [
        'microscopy-analysis.png',
        'experiment-analytics.png',
        'research-assistant.png',
        'evaluation-methodology.png',
        'generated-report.png',
        'dashboard-desktop.png',
        'dashboard-mobile.png',
      ],
    }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exit(1);
});
