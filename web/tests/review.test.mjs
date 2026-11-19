import test from 'node:test';
import assert from 'node:assert/strict';
import {present, render} from '../showcase/presentation.mjs';

// This DOM test double checks rendered text and links, without claiming browser/device coverage.
class Element {
  children = []; textContent = '';
  ownerDocument = {createElement: () => new Element()};
  append(...items) { this.children.push(...items); }
  flat() { return [this, ...this.children.flatMap(child => child.flat())]; }
}
const observation = (id, asset_identity) => ({id, asset_identity, observation:'Test reading', modality:'document'});
const candidate = {mechanism:'Candidate mechanism', status:'tentative', supporting_evidence_ids:['a','unlinked','fabricated'],
  contradicting_evidence_ids:['b'], excluded_as_unlinked:['unlinked'], missing_tests:['Check measurement']};
for (const [name, status, message, expected, links] of [
  ['conversation', 'complete', {content:'Hello'}, ['Hello'], []],
  ['investigation','complete',{hypotheses:[candidate], evidence:[observation('a','A')]},['Candidate mechanism','Check measurement'], ['a']],
  ['insufficient evidence','complete',{unresolved:['No measured vibration']},['No measured vibration'], []],
  ['contradiction','complete',{hypotheses:[candidate],evidence:[observation('a','A'),observation('b','A'),observation('unlinked','B')]},
    ['Contradictory evidence','Excluded from asset linkage'], ['a','b']],
  ['multiple assets','complete',{evidence:[observation('a','A'),observation('b','B')]},['A','B'], []],
  ['provider unavailable','error',{},['Local provider unavailable'], []],
  ['partial result','partial',{limitations:['Only one round completed']},['Only one round completed'], []]
]) test('saved response rendering: ' + name, () => {
  const job = {status, error:status==='error'?{message:'Local provider unavailable'}:undefined};
  const stored = message.content ? message : {metadata:{investigation:{...message,case:{evidence:message.evidence}}}};
  const view = present(job,stored);
  assert.equal(view.execution,status);
  const host = new Element(); render(host,view);
  for (const word of expected) assert.ok(host.flat().some(n=>n.textContent===word),word);
  assert.deepEqual(host.flat().filter(n=>n.href).map(n=>n.href),links.map(id=>'/api/v1/evidence/'+id));
});
