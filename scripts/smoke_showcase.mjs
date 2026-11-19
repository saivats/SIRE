/** Exercise the shipped upload handler against an explicitly selected local QA server.
 * The small DOM fixture below omits browser layout and device permissions.
 */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {basename, dirname, resolve} from 'node:path';

const [base, bundle] = process.argv.slice(2);
if (!base || !bundle) throw Error('Usage: node scripts/smoke_showcase.mjs http://127.0.0.1:QA_PORT PREPARED_BUNDLE');
const url = new URL(base);
if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || url.pathname !== '/' || url.username || url.password) {
  throw Error('Use the explicit IPv4 loopback origin of a fresh QA server');
}
const manifest = JSON.parse(await readFile(resolve(bundle, 'bundle.json'), 'utf8'));
const localFetch = globalThis.fetch;
globalThis.fetch = (path, options) => {
  if (typeof path !== 'string' || !path.startsWith('/api/v1/')) throw Error('Unexpected API path');
  return localFetch(url.origin + path, {...options, redirect:'error'});
};

class TestElement {
  children = [];
  textContent = '';
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  createTHead() { const node = new TestElement(); this.append(node); return node; }
  createTBody() { return this.createTHead(); }
  insertRow() { return this.createTHead(); }
  insertCell() { return this.createTHead(); }
  descendants() { return [this, ...this.children.flatMap(child => child.descendants())]; }
}
const nodes = new Map();
function getElementById(id) {
  if (!nodes.has(id)) nodes.set(id, new TestElement());
  return nodes.get(id);
}
globalThis.document = {getElementById, createElement: () => new TestElement()};
await import('../web/showcase/review.mjs');

for (const id of ['D01', 'D02', 'D03', 'D04']) {
  const files = [];
  for (const asset of manifest.instances[id].assets) {
    const path = resolve(bundle, 'inputs', asset.path);
    assert.equal(dirname(path), resolve(bundle, 'inputs', id));
    assert.match(path, /\.(csv|jpg|xlsx|pdf)$/i);
    const data = await readFile(path);
    assert.equal(createHash('sha256').update(data).digest('hex'), asset.sha256);
    files.push(new File([data], basename(path)));
  }
  getElementById('files').files = files;
  await getElementById('upload').onsubmit({preventDefault() {}});
  assert.equal(getElementById('status').textContent, files.length + ' distinct source files available · 0 processing errors.');
  const links = getElementById('records').descendants().filter(node => node.textContent === 'Source rows');
  assert.ok(links.length > 0);
  for (const item of links) {
    const reply = await fetch(item.href);
    assert.equal(reply.status, 200);
    assert.ok((await reply.json()).evidence.observation.rows.length);
  }
  console.log(id, files.length, 'receipts,', links.length, 'resolved measurement sources.');
}
