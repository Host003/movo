import assert from 'node:assert/strict';
import test from 'node:test';
import postcss from 'postcss';

import { adminDarkStyles } from './dark-style-plugin.mjs';

const from = '/workspace/apps/admin-web/src/views/auth/SetupPage.vue';

test('converts light custom surfaces and text while retaining light rules', async () => {
  const source = '.card { background: #fff; color: #17233d; border: 1px solid #e2e8f0; }';
  const { css } = await postcss([adminDarkStyles()]).process(source, { from });
  assert.match(css, /\.card \{ background: #fff; color: #17233d;/);
  assert.match(css, /html\.dark \.card \{ background: #192333; color: #e7edf7; border: 1px solid #354359;/);
});

test('preserves accent buttons and existing dark variants', async () => {
  const source = '.primary { background: #366aff; color: #fff; } html.dark .primary { background: #2757e6; }';
  const { css } = await postcss([adminDarkStyles()]).process(source, { from });
  assert.equal((css.match(/html\.dark \.primary/g) ?? []).length, 1);
  assert.match(css, /background: #2757e6/);
});

test('does not rewrite dependency styles', async () => {
  const source = '.card { background: #fff; }';
  const { css } = await postcss([adminDarkStyles()]).process(source, { from: '/workspace/node_modules/library/style.css' });
  assert.equal(css, source);
});

test('supports Windows source paths and named colors', async () => {
  const source = '.item { background: white; color: black; }';
  const { css } = await postcss([adminDarkStyles()]).process(source, { from: 'C:\\work\\apps\\admin-web\\src\\SetupPage.vue' });
  assert.match(css, /html\.dark \.item \{ background: #192333; color: #e7edf7;/);
});

test('keeps PDF canvas white', async () => {
  const source = '.pdf-page canvas { background: #fff; }';
  const { css } = await postcss([adminDarkStyles()]).process(source, { from });
  assert.equal(css, source);
});

test('darkens pale translucent surfaces but preserves colored highlights', async () => {
  const source = '.panel { background: rgba(247, 250, 255, .8); } .hero { background: rgba(255,255,255,.12); }';
  const { css } = await postcss([adminDarkStyles()]).process(source, { from });
  assert.match(css, /html\.dark \.panel \{ background: rgba\(25, 35, 51, .8\);/);
  assert.doesNotMatch(css, /html\.dark \.hero/);
});
