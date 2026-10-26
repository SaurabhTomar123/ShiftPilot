'use client';

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient } from '@/api/client';
import type { Schema } from '@/api/types';
import examples from '@/api/generated/staffing-template-examples.json';
import { minuteTime, timeMinute } from '@/lib/management';
import { templateProblem } from '@/lib/staffing-templates';
import { days } from '@/lib/types';
import { FormProblem } from './form-problem';
import { Button } from './primitives/button';

type Expansion = { key: string; body: Schema['ExpandStaffingRequest']; templateRevision: number };

export function StaffingTemplates({ client, outlet, week, skills, requirements, canEdit, fixtureMode, disabled, hasUnsavedRequirements, onExpanded, onBusy, onReloadRequirements }: {
  client: SchedulingClient; outlet: Schema['Outlet']; week: string; skills: Schema['Skill'][]; requirements: Schema['StaffingRequirements'] | null;
  canEdit: boolean; fixtureMode: boolean; disabled: boolean; hasUnsavedRequirements: boolean; onExpanded: (value: Schema['StaffingRequirements']) => void; onBusy: (value: boolean) => void; onReloadRequirements: () => void;
}) {
  const [base, setBase] = useState<Schema['StaffingTemplateSet'] | null>(null);
  const [items, setItems] = useState<Schema['StaffingTemplateBlock'][]>([]);
  const [day, setDay] = useState(0);
  const [skill, setSkill] = useState(skills[0]?.id ?? '');
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [needsReload, setNeedsReload] = useState(false);
  const [reviewed, setReviewed] = useState<Expansion | null>(null);
  const [uncertain, setUncertain] = useState<Expansion | null>(null);
  const [useBands, setUseBands] = useState(false);
  const active = useRef<AbortController | null>(null);
  const pendingExpansion = useRef<Expansion | null>(null);
  const setPending = (value: Expansion | null) => { pendingExpansion.current = value; setUncertain(value); };
  const dirty = !!base && JSON.stringify(base.items) !== JSON.stringify(items);
  const locked = busy || disabled || !!uncertain;
  const shown = items.map((item, index) => ({ item, index })).filter(({ item }) => item.weekday === day && item.skill_id === skill);
  const manualCount = requirements?.intervals.filter(value => value.source === 'manual').length ?? 0;
  function accept(value: Schema['StaffingTemplateSet']) {
    if (value.outlet_id !== outlet.id) throw new Error('The template response belongs to another outlet.');
    setBase(value); setItems(value.items); setNeedsReload(false); setReviewed(null);
  }
  useEffect(() => {
    const controller = new AbortController();
    client.staffingTemplates(outlet.id, controller.signal).then(value => { if (!controller.signal.aborted) { if (value.outlet_id !== outlet.id) throw new Error('The template response belongs to another outlet.'); setBase(value); setItems(value.items); setSkill(current => value.items.some(item => item.skill_id === current) ? current : value.items[0]?.skill_id ?? current); } }).catch(value => { if (!controller.signal.aborted) setError(value instanceof Error ? value : new Error('Could not load weekly templates.')); });
    return () => { controller.abort(); active.current?.abort(); onBusy(false); };
  }, [client, outlet.id, onBusy]);
  async function perform(task: (signal: AbortSignal) => Promise<void>, kind: 'read' | 'save' | 'expand' = 'read') {
    if (active.current) return;
    const controller = new AbortController(); active.current = controller; setBusy(true); onBusy(true); setError(null); setNotice('');
    try { await task(controller.signal); }
    catch (value) { if (!controller.signal.aborted) { setError(value instanceof Error ? value : new Error('The service could not be reached.')); if (kind === 'save') setNeedsReload(true); } }
    finally { if (!controller.signal.aborted) { active.current = null; setBusy(false); onBusy(!!pendingExpansion.current); } }
  }
  function change(index: number, patch: Partial<Schema['StaffingTemplateBlock']>) { setItems(old => old.map((item, i) => i === index ? { ...item, ...patch } : item)); setReviewed(null); setNotice(''); setError(null); }
  async function expand(intent: Expansion, signal: AbortSignal, retry = false) {
    if (!retry) {
      const current = await client.staffingTemplates(outlet.id, signal);
      if (current.revision !== intent.templateRevision || current.outlet_id !== outlet.id) { setReviewed(null); setNeedsReload(true); throw new Error('The saved weekly template changed. Reload it and review expansion again.'); }
    }
    setPending(intent);
    try {
      const value = await client.expandStaffing(outlet.id, week, intent.body, intent.key, signal);
      if (signal.aborted) return;
      if (value.outlet_id !== outlet.id || value.week_start !== week || value.demand_revision <= intent.body.base_demand_revision) throw new Error('The response does not confirm expansion for this outlet, week and revision. Check the dated requirements.');
      onExpanded(value); setPending(null); setReviewed(null); setNotice(`Expansion confirmed for ${week}: ${value.intervals.length} dated intervals, demand revision ${value.demand_revision}. Review manual overrides and coverage before generating a draft.`);
    } catch (value) { if (value instanceof ApiError && value.status < 500) { setPending(null); setReviewed(null); } throw value; }
  }
  return <details className="staffing-templates"><summary>Weekly staffing template</summary><section aria-label="Weekly staffing template editor">
    <h3>Plan a typical week</h3><p>Set recurring minimums and preferred targets in {outlet.timezone}. Saving the template does not change dated requirements or published assignments. Expand it separately for {week}.</p>
    {fixtureMode && <p className="contract-note">Synthetic examples: save the Saturday Grill increase, or expand the original template for 19 October. Expansion after changing the template, demand bands and manual-override combinations need a matching provider example or connected API.</p>}
    {!base && !error && <p role="status">Loading weekly template…</p>}
    <div className="template-filters"><label>Template weekday<select value={day} onChange={event => setDay(Number(event.target.value))}>{days.map((value, i) => <option key={value} value={i}>{value}</option>)}</select></label><label>Template skill<select value={skill} onChange={event => setSkill(event.target.value)}>{skills.map(value => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label></div>
    <form onSubmit={event => { event.preventDefault(); if (!base) return; const problem = templateProblem(items, skills.map(value => value.id)); if (problem) { setError(new Error(problem)); return; } perform(async signal => { const value = await client.saveStaffingTemplates(outlet.id, { base_revision: base.revision, items }, signal); if (!signal.aborted) { accept(value); setNotice('Weekly template saved. Dated requirements are unchanged until you explicitly expand.'); } }, 'save'); }}>
      <fieldset disabled={locked || !canEdit || !base || needsReload}><legend className="sr-only">Recurring staffing blocks</legend><p>Showing {shown.length} of {items.length} blocks. Saving replaces the complete outlet template, including other weekdays and skills.</p>
      <div className="template-blocks">{shown.map(({ item, index }, row) => <div className="template-block" key={index}>
        <label>From<input aria-label={`Template start ${row + 1}`} type="time" step={1800} required value={minuteTime(item.start_minute)} onChange={event => change(index, { start_minute: timeMinute(event.target.value) })} /></label>
        <label>Until<input aria-label={`Template end ${row + 1}`} type="time" step={1800} required disabled={item.end_minute === 1440} value={minuteTime(item.end_minute)} onChange={event => change(index, { end_minute: timeMinute(event.target.value) })} /></label>
        <label className="template-midnight"><input type="checkbox" checked={item.end_minute === 1440} onChange={event => change(index, { end_minute: event.target.checked ? 1440 : 1380 })} />End at midnight</label>
        <label>Minimum<input aria-label={`Template minimum ${row + 1}`} type="number" min={0} step={1} required value={Number.isNaN(item.minimum_required) ? '' : item.minimum_required} onChange={event => change(index, { minimum_required: event.target.value === '' ? NaN : Number(event.target.value) })} /></label>
        <label>Preferred<input aria-label={`Template preferred ${row + 1}`} type="number" min={0} step={1} required value={Number.isNaN(item.preferred_required) ? '' : item.preferred_required} onChange={event => change(index, { preferred_required: event.target.value === '' ? NaN : Number(event.target.value) })} /></label>
        <Button type="button" aria-label={`Remove block ${row + 1} from weekly template`} onClick={() => { setItems(old => old.filter((_, i) => i !== index)); setReviewed(null); setNotice(''); }}>Remove block</Button>
      </div>)}</div>
      {!shown.length && base && <p>No blocks for this weekday and skill. Add a block or change the filters.</p>}
      <p>Blocks stay within one weekday. Split overnight staffing across two weekdays. Minimum staffing is required; preferred staffing is the target.</p>
      <Button type="button" disabled={!skill || items.length >= 2000} onClick={() => { setItems(old => [...old, { weekday: day, skill_id: skill, start_minute: 540, end_minute: 1020, minimum_required: 1, preferred_required: 1 }]); setReviewed(null); setNotice(''); }}>Add template block</Button>
      {fixtureMode && <Button type="button" onClick={() => { setItems(examples.items as Schema['StaffingTemplateBlock'][]); setDay(5); setSkill(examples.items.find(value => value.weekday === 5 && value.start_minute === 1080 && value.minimum_required === 2 && value.preferred_required === 4)?.skill_id ?? skill); setReviewed(null); setNotice('Saturday Grill example loaded for review; nothing has been saved.'); }}>Load Saturday Grill example</Button>}
      {!items.length && <p>Saving an empty set removes the recurring template. Existing dated requirements stay in place.</p>}
      </fieldset>
      <div className="management-form-actions">{canEdit && <Button type="submit" variant="primary" disabled={locked || !base || !dirty || needsReload}>Save weekly template</Button>}<Button type="button" disabled={locked} onClick={() => perform(async signal => { const value = await client.staffingTemplates(outlet.id, signal); if (!signal.aborted) { accept(value); setNotice('Weekly template reloaded. Unsaved template edits were replaced.'); } })}>Reload weekly template</Button><span>Template revision {base?.revision ?? 'not loaded'}.</span></div>
    </form>
    {error && <FormProblem error={error} />}{notice && <p className="save-notice" role="status">{notice}</p>}
    {needsReload && <p role="alert">The template save or revision was not confirmed. Reload the weekly template before another save or expansion; no automatic retry was sent.</p>}
    <section className="template-expansion" aria-label="Expand weekly template"><h3>Use the saved template for this week</h3><p>Expansion writes dated staffing requirements for {week}. It replaces template and demand-band rows while preserving manual overrides and other retained sources. It does not generate or publish a schedule.</p>
      {hasUnsavedRequirements && <p role="alert">Dated staffing has unsaved changes. Save or reload those changes before expanding.</p>}{dirty && <p>Save or reload your template edits before reviewing expansion.</p>}
      <label className="template-bands"><input type="checkbox" disabled={locked || !canEdit} checked={useBands} onChange={event => { setUseBands(event.target.checked); setReviewed(null); }} />Use demand bands where order counts are available</label><p>Demand bands are saved order-volume-to-staffing rules. Enabling them does not create a forecast or import new observations.</p>
      <Button disabled={locked || !canEdit || !base || !base.items.length || !requirements || dirty || hasUnsavedRequirements || needsReload} onClick={() => setReviewed({ key: crypto.randomUUID(), body: { base_demand_revision: requirements!.demand_revision, use_demand_bands: useBands }, templateRevision: base!.revision })}>Review expansion request</Button>
      {reviewed && !uncertain && !dirty && !hasUnsavedRequirements && requirements?.demand_revision === reviewed.body.base_demand_revision && <div className="surface-note"><h4>Review before expanding</h4><p>Outlet: {outlet.name}. Week: {week}. Saved template revision {reviewed.templateRevision}; demand revision {reviewed.body.base_demand_revision}. {base?.items.length} saved template blocks and {manualCount} current manual intervals. Demand bands: {reviewed.body.use_demand_bands ? 'enabled' : 'disabled'}.</p><p>This is a request summary, not a generated-interval preview. The server uses the saved template current when expansion runs and preserves manual overrides.</p><Button variant="primary" disabled={locked} onClick={() => perform(signal => expand(reviewed, signal), 'expand')}>Expand saved template into this week</Button></div>}
      {uncertain && <div role="alert"><p>The expansion result is uncertain. Check dated staffing, or explicitly retry this same request and key. Do not save another template or dated change while it is unresolved.</p><Button disabled={busy || disabled} onClick={() => perform(async signal => { const value = await client.staffing(outlet.id, week, signal); if (!signal.aborted) setNotice(`Current dated demand revision is ${value.demand_revision}. A newer revision alone does not prove this expansion completed; retry the same key to confirm its result.`); })}>Check dated staffing</Button><Button disabled={busy || disabled} onClick={() => perform(signal => expand(uncertain, signal, true), 'expand')}>Retry same expansion</Button></div>}
      {!uncertain && error instanceof ApiError && error.detail.code === 'stale_version' && <Button disabled={locked} onClick={onReloadRequirements}>Reload dated requirements</Button>}
    </section>
  </section></details>;
}
