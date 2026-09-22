import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { once } from 'node:events';
import { chromium } from 'playwright';

const python = existsSync('.venv/bin/python') ? '.venv/bin/python' : 'python3';
const server = spawn(python, ['tests/browser/serve_environment_view.py'], {
    cwd: process.cwd(),
    stdio: ['ignore', 'pipe', 'inherit'],
});

async function firstLine(stream) {
    let value = '';
    for await (const chunk of stream) {
        value += chunk;
        const newline = value.indexOf('\n');
        if (newline !== -1) return value.slice(0, newline).trim();
    }
    throw new Error('EnvironmentView fixture server exited before reporting its port');
}

let browser;
try {
    const port = await firstLine(server.stdout);
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    const consoleErrors = [];
    page.on('console', (message) => {
        if (message.type() === 'error') consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    await page.goto(`http://127.0.0.1:${port}/`);
    await page.waitForFunction(() => window.fixtureReady === true);

    assert.equal(await page.getByRole('button', { name: 'Toggle exploration veil' }).textContent(), 'Toggle Veil');
    assert.equal(await page.locator('#btn-fog-toggle').count(), 0);
    assert.equal((await page.content()).includes('\u{1F441}'), false);

    const veilVisibleBefore = await page.evaluate(() => window.environmentView.explorationInstancedMesh.visible);
    await page.getByRole('button', { name: 'Toggle exploration veil' }).click();
    const veilVisibleAfter = await page.evaluate(() => window.environmentView.explorationInstancedMesh.visible);
    assert.equal(veilVisibleBefore, true);
    assert.equal(veilVisibleAfter, false);

    const distanceBefore = await page.evaluate(() =>
        window.environmentView.camera.position.distanceTo(window.environmentView.controls.target));
    await page.getByRole('button', { name: 'Zoom in' }).click();
    const distanceAfter = await page.evaluate(() =>
        window.environmentView.camera.position.distanceTo(window.environmentView.controls.target));
    assert.ok(distanceAfter < distanceBefore);
    await page.getByRole('button', { name: 'Reset view' }).click();

    await page.evaluate(() => {
        window.environmentView.update({
            ...window.initialWorld,
            agents: [window.initialWorld.agents[0]],
            obstacles: [{ id: 'tower', x: 220, y: 210, z: 0, w: 24, h: 150 }],
        });
    });
    assert.equal(await page.evaluate(() => window.environmentView.agentMeshes.size), 1);
    assert.deepEqual(
        await page.evaluate(() => {
            const record = window.environmentView.obstacleMeshes.get('tower');
            return [record.w, record.h, record.mesh.position.x, record.mesh.position.z];
        }),
        [24, 150, 220, 75],
    );

    const validationMessage = await page.evaluate(() => {
        try {
            window.environmentView.update({ ...window.initialWorld, nest: { x: 1, y: 2 } });
            return '';
        } catch (error) {
            return error.message;
        }
    });
    assert.match(validationMessage, /world\.nest\.z must be a finite number/);

    await page.evaluate(() => {
        const viewer = document.getElementById('viewer');
        viewer.style.width = '500px';
        viewer.style.height = '320px';
    });
    await page.waitForFunction(() => Math.abs(window.environmentView.camera.aspect - (500 / 320)) < 0.01);

    await page.evaluate(() => {
        window.environmentView.dispose();
        window.environmentView.resize();
    });
    assert.equal(await page.locator('#viewer canvas').count(), 0);
    assert.equal(await page.locator('#viewer .environment-view__controls').count(), 0);
    assert.equal(await page.locator('#viewer.environment-view').count(), 0);
    assert.deepEqual(consoleErrors, []);
} finally {
    await browser?.close();
    server.kill('SIGTERM');
    await Promise.race([once(server, 'exit'), new Promise((resolve) => setTimeout(resolve, 2000))]);
}
