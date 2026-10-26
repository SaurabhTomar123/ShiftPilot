'use client';
/* eslint jsx-a11y/no-noninteractive-tabindex: ["error", { "roles": ["region"] }] */

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient } from '@/api/client';
import type { Schema } from '@/api/types';
import examples from '@/api/generated/rule-examples.json';
import { minuteTime, timeMinute } from '@/lib/management';
import { days } from '@/lib/types';
import { checkedRule, ruleIdentity, ruleImpactTime } from '@/lib/rules';
import { FormProblem } from './form-problem';
import { Button } from './primitives/button';

type Props = { client: SchedulingClient; me: Schema['Me']; outlet: Schema['Outlet']; outlets: Schema['Outlet'][]; fixtureMode: boolean };
type Reviewed = { request: Schema['RuleDefinition']; preview: Schema['RulePreview'] };
type Pending = { request: Schema['RuleDefinition']; key: string };
const definitionOf = (value: Schema['SchedulingRule']): Schema['RuleDefinition'] => ({ rule_type: value.rule_type, scope_level: value.scope_level, scope: value.scope, parameters: value.parameters, hard: value.hard ?? true, overrides_rule_id: value.overrides_rule_id ?? null, source_text: value.source_text ?? null });

export function SchedulingRules(props: Props) {
  return props.me.capabilities.includes('manage_employees') ? <RulesContent {...props} /> : <p>Scheduling rules require employee-management access.</p>;
}

function RulesContent({ client, me, outlet, outlets, fixtureMode }: Props) {
  const owner = me.role === 'owner';
  const [data, setData] = useState<{ rules: Schema['SchedulingRule'][]; employees: Schema['Employee'][] } | null>(null);
  const [definition, setDefinition] = useState<Schema['RuleDefinition']>({ rule_type: 'max_days_per_week', scope_level: 'outlet', scope: { outlet_id: outlet.id }, parameters: { days: 5 }, hard: true, overrides_rule_id: null, source_text: null });
  const [reviewed, setReviewed] = useState<Reviewed | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [needsReload, setNeedsReload] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const action = useRef<AbortController | null>(null);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  async function read(signal: AbortSignal) {
    const [rules, first] = await Promise.all([client.rules(true, signal), client.employees(outlet.id, undefined, signal)]);
    const employees = [...first.items]; let cursor = first.next_cursor; const seen = new Set<string>();
    while (cursor) { if (seen.has(cursor) || seen.size >= 50) throw new Error('The employee list could not be completed. Reload before targeting a person.'); seen.add(cursor); const page = await client.employees(outlet.id, cursor, signal); employees.push(...page.items); cursor = page.next_cursor; }
    if (employees.some(value => value.home_outlet_id !== outlet.id)) throw new Error('Employee choices include another outlet. Reload rules.');
    return { rules: rules.items, employees };
  }
  useEffect(() => { const controller = new AbortController(); read(controller.signal).then(value => { if (!controller.signal.aborted) setData(value); }).catch(value => { if (!controller.signal.aborted) setError(value instanceof Error ? value : new Error('Could not load scheduling rules.')); }); return () => { controller.abort(); action.current?.abort(); };
    // The parent remounts rules for outlet, persona and demo-outcome changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, outlet.id]);
  async function perform(task: (signal: AbortSignal) => Promise<void>) {
    if (action.current) return;
    const controller = new AbortController(); action.current = controller; setBusy(true); setError(null); setNotice('');
    try { await task(controller.signal); } catch (value) { if (!controller.signal.aborted) setError(value instanceof Error ? value : new Error('The scheduling service could not be reached.')); }
    finally { if (!controller.signal.aborted) { action.current = null; setBusy(false); } }
  }
  const change = (patch: Partial<Schema['RuleDefinition']>) => { setDefinition(old => ({ ...old, ...patch })); setReviewed(null); setError(null); setNotice(''); setArchiveId(null); };
  const loadDefinition = (value: Schema['RuleDefinition']) => { setDefinition(structuredClone(value)); setReviewed(null); setError(null); setNotice('Review this rule with a fresh preview before saving.'); setArchiveId(null); };
  const updateRule = (value: Schema['SchedulingRule']) => setData(old => old && ({ ...old, rules: [...old.rules.filter(rule => rule.id !== value.id), value] }));
  async function save(intent: Pending, signal: AbortSignal) {
    setPending(intent);
    try {
      const value = await client.createRule(intent.request, intent.key, signal);
      if (signal.aborted) return;
      if (value.status !== 'active' || ruleIdentity(definitionOf(value)) !== ruleIdentity(intent.request)) throw new Error('The response does not confirm this exact rule. Check the saved rules or retry the same request.');
      updateRule(value); setPending(null); setReviewed(null); setNotice('Rule saved. Existing published assignments have not been moved. The next generation or repair uses the active rules.');
    } catch (value) { if (value instanceof ApiError && value.status < 500) { setPending(null); setReviewed(null); } throw value; }
  }
  if (!data) return <section>{error ? <FormProblem error={error} /> : <p role="status">Loading rules and employee choices…</p>}<Button disabled={busy} onClick={() => perform(async signal => { const value = await read(signal); if (!signal.aborted) setData(value); })}>Reload scheduling rules</Button></section>;
  const locked = busy || !!pending || needsReload;
  const canArchive = (value: Schema['SchedulingRule']) => owner || (value.scope_level === 'outlet' && value.scope.outlet_id === me.outlet_id) || (value.scope_level === 'employee' && data.employees.some(person => person.id === value.scope.employee_id && person.home_outlet_id === me.outlet_id));
  const scopeName = (value: Schema['RuleDefinition']) => value.scope_level === 'organization' ? 'Organization: all outlets' : value.scope_level === 'tag' ? `Tag: ${value.scope.tag} across outlets` : value.scope_level === 'outlet' ? `Outlet: ${outlets.find(item => item.id === value.scope.outlet_id)?.name ?? 'Referenced outlet'}` : `Person: ${data.employees.find(item => item.id === value.scope.employee_id)?.name ?? 'employee outside the selected outlet (see reference)'}`;
  const visibleRules = data.rules.filter(value => includeArchived || value.status !== 'archived');
  const weekdayValues = Array.isArray(definition.parameters.weekdays) ? definition.parameters.weekdays as number[] : [];
  const latest = Number(definition.parameters.latest_end_minute ?? 1260);
  const archiveTarget = data.rules.find(value => value.id === archiveId);
  return <section className="scheduling-rules" aria-label="Scheduling rules workspace">
    <div className="rules-boundary"><h2>Rules for future planning</h2><p>Preview affected people, rule conflicts and upcoming shift impacts before saving. Existing published schedules stay in place; the next generation or repair uses the saved rules.</p><p>Availability and absence facts still apply. A more specific rule becomes an exception only when it explicitly references the rule it overrides.</p></div>
    {fixtureMode && <p className="contract-note">Synthetic examples cover the owner’s student latest-finish rule and Rohit’s conflict. Suggested-exception previews, other rule types/scopes and real shift-impact examples need matching records or a connected API.</p>}
    {error && <FormProblem error={error} />}{notice && <p role="status" className="save-notice">{notice}</p>}
    <div className="rules-list-heading"><h2>Saved rules</h2><Button disabled={busy} onClick={() => perform(async signal => { const value = await read(signal); if (!signal.aborted) { setData(value); setNeedsReload(false); setReviewed(null); setArchiveId(null); setNotice('Rules reloaded. Review active and archived records before another change.'); } })}>Reload saved rules</Button></div>
    <label className="rules-archived-filter"><input type="checkbox" checked={includeArchived} onChange={event => setIncludeArchived(event.target.checked)} />Include archived rules</label>
    <p>The catalog can include rules spanning several outlets. The outlet selector controls employee choices and new outlet rules. Organization and tag changes require an owner.</p>
    {visibleRules.length ? <ul className="saved-rules">{visibleRules.map(value => <li key={value.id}><article><h3>{value.summary}</h3><p>{scopeName(value)}. Status: <strong>{value.status}</strong>.</p>{value.source_text && <p>{value.source_text}</p>}{value.overrides_rule_id && <p>This rule is an explicit exception to another rule.</p>}<details><summary>Rule reference</summary><p>Rule: {value.id}{value.scope.employee_id && `; person: ${value.scope.employee_id}`}{value.overrides_rule_id && `; overrides: ${value.overrides_rule_id}`}</p></details>{value.status !== 'archived' && (canArchive(value) ? <Button disabled={locked} onClick={() => { setArchiveId(value.id); setError(null); }}>Archive rule</Button> : <p>An owner manages this rule’s scope.</p>)}</article></li>)}</ul> : <p>No rules in this view. Include archived rules to inspect earlier records.</p>}
    {archiveTarget && <section className="rules-archive-confirm" aria-label="Archive rule decision"><h3>Archive this rule?</h3><p>{archiveTarget.summary}. {scopeName(archiveTarget)}. Future planning will stop applying it. Published assignments remain unchanged.</p><Button disabled={locked} onClick={() => perform(async signal => { try { const value = await client.archiveRule(archiveTarget.id, signal); if (signal.aborted) return; if (value.id !== archiveTarget.id || value.status !== 'archived') throw new Error('The response does not confirm this rule was archived. Reload saved rules.'); updateRule(value); setArchiveId(null); setReviewed(null); setNotice('Rule archived. Published assignments remain unchanged.'); } catch (value) { if (!(value instanceof ApiError) || value.status >= 500) { setNeedsReload(true); setIncludeArchived(true); setArchiveId(null); } throw value; } })}>Confirm archive rule</Button><Button disabled={busy} onClick={() => setArchiveId(null)}>Keep rule</Button></section>}
    {needsReload && <p role="alert">The archive result is not confirmed. Reload saved rules before another write; it has not been retried.</p>}
    <section className="rule-editor" aria-label="New scheduling rule"><h2>Define a scheduling rule</h2><form onSubmit={event => { event.preventDefault(); let request: Schema['RuleDefinition']; try { request = checkedRule(definition, owner, outlet.id, data.employees.map(value => value.id)); } catch (value) { setError(value instanceof Error ? value : new Error('Check the rule fields.')); return; } perform(async signal => { setReviewed(null); const preview = await client.previewRule(request, signal); if (!signal.aborted) { const returned = checkedRule(preview.rule, owner, outlet.id, data.employees.map(value => value.id)); if (ruleIdentity(returned) !== ruleIdentity(request)) throw new Error('The preview does not match these rule fields. Preview the current inputs again.'); setReviewed({ request, preview: { ...preview, rule: returned } }); requestAnimationFrame(() => previewHeading.current?.focus()); } }); }}>
      <fieldset disabled={locked}><legend className="sr-only">Rule definition</legend><div className="rule-fields">
        <label>Rule type<select value={definition.rule_type} onChange={event => change({ rule_type: event.target.value as Schema['RuleDefinition']['rule_type'], overrides_rule_id: null, parameters: event.target.value === 'max_days_per_week' ? { days: 5 } : { latest_end_minute: 1260, weekdays: [0, 1, 2, 3, 4] } })}><option value="max_days_per_week">Maximum working days per week</option><option value="max_shift_end_time">Latest shift finish</option></select></label>
        <label>Applies to<select value={definition.scope_level} onChange={event => { const scope = event.target.value as Schema['RuleDefinition']['scope_level']; change({ scope_level: scope, scope: scope === 'organization' ? {} : scope === 'outlet' ? { outlet_id: outlet.id } : scope === 'tag' ? { tag: '' } : { employee_id: data.employees[0]?.id ?? '' }, overrides_rule_id: null }); }}><option value="outlet">Selected outlet</option><option value="employee">One person</option>{owner && <><option value="organization">Entire organization</option><option value="tag">Employee tag across outlets</option></>}</select></label>
        {definition.scope_level === 'employee' && <label>Person<select value={definition.scope.employee_id} onChange={event => change({ scope: { employee_id: event.target.value }, overrides_rule_id: null })}><option value="">Choose a person</option>{data.employees.map(value => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>}
        {definition.scope_level === 'tag' && <label>Employee tag<input maxLength={100} required value={definition.scope.tag} onChange={event => change({ scope: { tag: event.target.value }, overrides_rule_id: null })} /></label>}
        {definition.rule_type === 'max_days_per_week' ? <label>Maximum working days<input type="number" min={1} max={7} step={1} required value={Number.isNaN(Number(definition.parameters.days)) ? '' : Number(definition.parameters.days)} onChange={event => change({ parameters: { days: event.target.value === '' ? NaN : Number(event.target.value) } })} /></label> : <><label>Latest finish<input type="time" step={1800} required disabled={latest === 1440} value={minuteTime(latest)} onChange={event => change({ parameters: { ...definition.parameters, latest_end_minute: timeMinute(event.target.value) } })} /></label><label className="rule-midnight"><input type="checkbox" checked={latest === 1440} onChange={event => change({ parameters: { ...definition.parameters, latest_end_minute: event.target.checked ? 1440 : 1260 } })} />Allow finish at midnight</label></>}
      </div>{definition.rule_type === 'max_shift_end_time' && <fieldset className="rule-weekdays"><legend>Finish limit applies on</legend>{days.map((day, index) => <label key={day}><input type="checkbox" checked={weekdayValues.includes(index)} onChange={event => change({ parameters: { ...definition.parameters, weekdays: event.target.checked ? [...weekdayValues, index].sort() : weekdayValues.filter(value => value !== index) } })} />{day}</label>)}</fieldset>}
      <label className="rule-notes">Rule notes (optional)<textarea maxLength={500} value={definition.source_text ?? ''} onChange={event => change({ source_text: event.target.value || null })} /></label><p>Rules are required constraints. Finish limits use each affected outlet’s local time.</p>{definition.overrides_rule_id && <div className="surface-note"><p>This definition includes an explicit exception reference: {definition.overrides_rule_id}. Changes to type or scope should be reviewed again.</p><Button type="button" onClick={() => change({ overrides_rule_id: null })}>Remove exception reference</Button></div>}
      <Button type="submit" variant="primary">Preview rule impact</Button>
      {fixtureMode && <div className="rule-examples">{owner && <Button type="button" onClick={() => loadDefinition(examples.student as Schema['RuleDefinition'])}>Load student finish-limit example</Button>}<Button type="button" onClick={() => loadDefinition(examples.conflict as Schema['RuleDefinition'])}>Load Rohit conflict example</Button></div>}
      </fieldset>
    </form></section>
    {reviewed && <section className="rule-preview" aria-label="Rule impact preview"><h2 ref={previewHeading} tabIndex={-1}>Review rule impact</h2><h3>{reviewed.preview.summary}</h3><p>{scopeName(reviewed.preview.rule)}. Preview only: nothing has been saved or moved.</p><p>{reviewed.preview.affected.length} affected people returned. This is a server-reported scope, not a browser eligibility calculation.</p><ul>{reviewed.preview.affected.map(value => <li key={value.employee_id}>{value.name}</li>)}</ul>
      {reviewed.preview.conflicts.length > 0 && <div className="rule-conflicts"><h3>Conflicts to resolve</h3>{reviewed.preview.conflicts.map((conflict, index) => <article key={`${conflict.rule_id}:${index}`}><h4>{conflict.rule_name}</h4><p>{conflict.message}</p><p>People in both rules: {conflict.employees.join(', ')}.</p>{conflict.suggested_exception && <Button disabled={locked} onClick={() => loadDefinition(conflict.suggested_exception!)}>Use suggested exception for {conflict.employees.join(', ')}</Button>}</article>)}</div>}
      <h3>Upcoming published shifts to review</h3><p>Up to 50 impacts are returned. Times below retain each shift’s UTC offset. Saving a rule does not move these assignments.</p>{reviewed.preview.impact.length ? <div className="review-table-scroll" role="region" aria-label="Rule shift impacts" tabIndex={0}><table><thead><tr><th scope="col">Person</th><th scope="col">From</th><th scope="col">Until</th><th scope="col">Impact</th></tr></thead><tbody>{reviewed.preview.impact.map((value, index) => <tr key={`${value.logical_shift_id}:${index}`}><th scope="row">{value.name}</th><td>{ruleImpactTime(value.start_at)}</td><td>{ruleImpactTime(value.end_at)}</td><td>{value.message}<details><summary>Assignment reference</summary>{value.logical_shift_id}</details></td></tr>)}</tbody></table></div> : <p>No upcoming published-shift impacts were returned.</p>}
      {!reviewed.preview.valid && <p role="alert">This rule is not valid for saving. Resolve the reported conflicts and preview again.</p>}
      <Button variant="primary" disabled={locked || !reviewed.preview.valid || reviewed.preview.conflicts.length > 0} onClick={() => perform(signal => save({ request: reviewed.preview.rule, key: crypto.randomUUID() }, signal))}>Save reviewed rule</Button>
    </section>}
    {pending && <section className="surface-note" aria-label="Unconfirmed rule save"><p>The save result is uncertain. Read saved rules or explicitly retry this exact rule and key. Other writes are blocked until this result is confirmed.</p><Button disabled={busy} onClick={() => perform(async signal => { const value = await client.rules(true, signal); if (!signal.aborted) { setData(old => old && { ...old, rules: value.items }); setNotice('Saved rules read. Matching text alone does not prove this request completed; retry the same key to confirm its result.'); } })}>Check rule save</Button><Button disabled={busy} onClick={() => perform(signal => save(pending, signal))}>Retry same rule save</Button></section>}
  </section>;
}
