/** Convert saved SIRE records to display fields. Only case evidence can supply a source link. */
export function present(job, message) {
  const meta = message?.metadata ?? {};
  const report = meta.investigation;
  const evidence = report?.case?.evidence ?? meta.evidence ?? [];
  const sources = new Map(evidence.map(item => [item.id, item]));
  function references(ids, excluded) {
    return (ids ?? []).filter(id => sources.has(id) && !excluded.includes(id));
  }
  return {
    execution: job?.status ?? message?.status ?? 'unavailable',
    error: job?.error?.message ?? report?.followup_error?.message,
    summary: message?.content ?? '',
    caseId: meta.investigation_id,
    assets: [...new Set(evidence.map(item => item.asset_identity).filter(Boolean))],
    evidence,
    hypotheses: (report?.hypotheses ?? []).map(h => ({
      mechanism: h.mechanism, status: h.status, checks: h.missing_tests ?? [],
      support: references(h.supporting_evidence_ids, h.excluded_as_unlinked ?? []),
      conflict: references(h.contradicting_evidence_ids, h.excluded_as_unlinked ?? []),
      excluded: h.excluded_as_unlinked ?? []
    })),
    limitations: [...(report?.limitations ?? []), ...(report?.unresolved ?? [])],
    speech: meta.speech_text ?? ''
  };
}

export function render(host, view) {
  const make = (tag, text) => { const n = host.ownerDocument.createElement(tag); n.textContent = text; return n; };
  const section = (title, values) => {
    if (!values.length) return;
    host.append(make('h4', title));
    for (const v of values) host.append(make('p', v));
  };
  if (view.caseId) host.append(make('small', 'Case ' + view.caseId));
  section('Asset scope', view.assets);
  if (view.summary) host.append(make('pre', view.summary));
  for (const item of view.evidence) {
    const d = make('details', '');
    d.append(make('summary', item.asset_identity || item.modality || 'Observation'),
      make('p', item.observation), make('small', [item.kind, item.locator, item.id].filter(Boolean).join(' · ')));
    host.append(d);
  }
  for (const h of view.hypotheses) {
    host.append(make('h3', h.mechanism), make('p', 'Engineering status · ' + h.status));
    for (const [title, ids] of [['Supporting evidence', h.support], ['Contradictory evidence', h.conflict]]) {
      if (ids.length) host.append(make('h4', title));
      for (const id of ids) {
        const a = make('a', id); a.href = '/api/v1/evidence/' + encodeURIComponent(id);
        const p = make('p', ''); p.append(a); host.append(p);
      }
    }
    section('Excluded from asset linkage', h.excluded);
    section('Next checks', h.checks);
  }
  section('Limitations and unresolved questions', view.limitations);
  if (view.error) host.append(make('p', view.error));
  if (view.speech) host.append(make('p', view.speech));
}
