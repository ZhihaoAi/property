const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const NODE_TEST_FILES = [
  'tests/dashboard.bootstrap.spec.js',
  'tests/dashboard.owner-pool.spec.js',
  'tests/test-entrypoints.spec.js',
  'tests/wealth-model.spec.js',
  'tests/wealth-workbook.spec.mjs',
];

test('npm test runs node unit tests before Playwright e2e', () => {
  const packageJson = JSON.parse(fs.readFileSync('./package.json', 'utf8'));

  assert.equal(packageJson.scripts.test, 'npm run test:unit && npm run test:e2e');
  assert.match(packageJson.scripts['test:unit'], /^node --test /);
  NODE_TEST_FILES.forEach((file) => {
    assert.match(packageJson.scripts['test:unit'], new RegExp(file.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  });
});

test('Playwright e2e discovery ignores node:test specs', () => {
  const config = require('../playwright.config.js');
  const ignored = new Set(config.testIgnore || []);

  NODE_TEST_FILES.forEach((file) => {
    assert.ok(ignored.has(`**/${file}`), `${file} must be ignored by Playwright`);
  });
});
