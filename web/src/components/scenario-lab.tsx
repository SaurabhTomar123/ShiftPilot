'use client';
/* eslint jsx-a11y/no-noninteractive-tabindex: ["error", { "roles": ["region"] }] */

import { useEffect, useRef, useState } from 'react';
import { ApiError, SchedulingClient, watchRun } from '@/api/client';
import { burdenNumber, formatMoney, percent, runMessage, strategyName } from '@/api/presentation';
import examples from '@/api/generated/scenario-examples.json';
import type { Schema } from '@/api/types';
import { scenarioMatches, scenarioRunMatches } from '@/lib/scenario';
import { DecisionEvidence, FairnessBreakdown, PortfolioDetails } from './decision-evidence';
import { ScenarioEventEditor, ScenarioEventList } from './scenario-events';
import { ProposalReview } from './candidate-review';
import { Button } from './primitives/button';
import { FormProblem } from './management';

export function ScenarioLab({ client, outlet, week, skills, capabilities, fixtureMode }: {
  client: SchedulingClient; outlet: Schema['Outlet']; week: string; skills: Schema['Skill'][]; capabilities: Schema['Me']['capabilities']; fixtureMode: boolean;
}) {
  const [data, setData] = useState<{ list: Schema['Scenario'][]; schedule: Schema['ScheduleWeek'] } | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Schema['Scenario'] | null>(null);
  const [title, setTitle] = useState('');
  const [events, setEvents] = useState<Schema['ScenarioEventIn'][]>([]);
  const [run, setRun] = useState<Schema['OptimizationRun'] | null>(null);
  const [trackedId, setTrackedId] = useState<string | null>(null);
  const [profile, setProfile] = useState<Schema['ScenarioRunRequest']['strategy']>('balanced');
  const [draft, setDraft] = useState<Schema['ScheduleVersion'] | null>(null);
  const [candidate, setCandidate] = useState('');
  const [discard, setDiscard] = useState(false);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [conversion, setConversion] = useState<{ scenario: string; candidate: string; key: string } | null>(null);
  const [eventsChanged, setEventsChanged] = useState(false);
  const [notice, setNotice] = useState('');
  const active = useRef(false);
  const life = useRef<AbortController | null>(null);
  const keys = useRef(new Map<string, string>());
  const heading = useRef<HTMLHeadingElement>(null);
  const showCosts = capabilities.includes('view_costs');
  const canConvert = capabilities.includes('publish');
  const keyFor = (identity: string) => { if (!keys.current.has(identity)) keys.current.set(identity, crypto.randomUUID()); return keys.current.get(identity)!; };
  const update = (value: Schema['Scenario']) => {
    if (!scenarioMatches(value, outlet.id, week)) throw new Error('This scenario belongs to another outlet or week. Reload Scenario Lab.');
    setSelected(value); setData(old => old && ({ ...old, list: [value, ...old.list.filter(item => item.id !== value.id)] }));
  };
  async function read(signal: AbortSignal) {
    const [list, schedule] = await Promise.all([client.scenarios(outlet.id, week, signal), client.schedule(outlet.id, week, signal)]);
    if (list.items.some(value => !scenarioMatches(value, outlet.id, week))) throw new Error('The scenario list contains another outlet or week.');
    return { list: list.items, schedule };
  }
  async function load(signal: AbortSignal) { const value = await read(signal); if (!signal.aborted) setData(value); }
  useEffect(() => {
    const controller = new AbortController(); life.current = controller;
    read(controller.signal).then(value => { if (!controller.signal.aborted) setData(value); }).catch(value => { if (!controller.signal.aborted) setError(value instanceof Error ? value : new Error('Could not load Scenario Lab.')); });
    return () => controller.abort();
    // The parent remounts this screen for each outlet, week and session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, outlet.id, week]);
  async function perform(task: (signal: AbortSignal) => Promise<void>, unkeyedWrite = false) {
    if (active.current || !life.current) return;
    active.current = true; setBusy(true); setError(null);
    const signal = life.current.signal;
    try { await task(signal); }
    catch (value) { if (!signal.aborted) { setError(value instanceof Error ? value : new Error('The scheduling service could not be reached.')); if (unkeyedWrite) setNeedsRefresh(true); } }
    finally { if (!signal.aborted) { active.current = false; setBusy(false); } }
  }
  async function open(id: string, signal: AbortSignal) {
    const value = await client.scenario(id, signal); if (signal.aborted) return;
    update(value); setRun(null); setTrackedId(value.latest_run_id); setCandidate(''); setDraft(null); setDiscard(false); setEventsChanged(!!value.latest_run_id); setConversion(null);
    requestAnimationFrame(() => heading.current?.focus());
    if (value.latest_run_id) { const read = await client.run(value.latest_run_id, signal); if (!signal.aborted) { if (!scenarioRunMatches(read, value)) throw new Error('This run does not belong to the selected what-if.'); setRun(read); } }
  }
  async function track(value: Schema['Scenario'], initial: Schema['OptimizationRun'], signal: AbortSignal) {
    if (!scenarioRunMatches(initial, value)) throw new Error('This run does not match the scenario and its base version.');
    setTrackedId(initial.id);
    await watchRun(client, initial, { signal, onUpdate: read => { if (!scenarioRunMatches(read, value)) throw new Error('The status read belongs to another scenario.'); setRun(read); } });
    const current = await client.scenario(value.id, signal); if (!signal.aborted) { update(current); if (JSON.stringify(current.events) !== JSON.stringify(value.events)) { setEventsChanged(true); setCandidate(''); } }
  }
  async function convert(pending: { scenario: string; candidate: string; key: string }, signal: AbortSignal) {
    try {
      const value = await client.convertScenario(pending.scenario, { candidate_id: pending.candidate }, pending.key, signal);
      if (!selected || value.status !== 'draft' || value.source !== 'scenario' || value.schedule_id !== selected.schedule_id || value.base_version_id !== selected.base_version_id) throw new Error('Conversion did not confirm a scenario draft for this schedule. Check its saved result.');
      return value;
    } catch (value) { if (value instanceof ApiError && value.status < 500) setConversion(null); throw value; }
  }
  function openConvertedRead(value: Schema['ScheduleVersion']) {
    if (!selected || value.source !== 'scenario' || value.schedule_id !== selected.schedule_id) throw new Error('The returned version does not match this converted scenario.');
    if (value.status !== 'draft') { setDraft(null); setNotice(`The converted version is now ${value.status}. Open Schedule or History to inspect its current state.`); }
    else setDraft(value);
  }
  const editable = selected?.status === 'open' && !needsRefresh && !conversion;
  const activeRun = run && ['queued', 'running'].includes(run.job_state);
  const usableRun = selected && run && selected.latest_run_id === run.id && scenarioRunMatches(run, selected) && !eventsChanged && !run.candidates_expired && run.job_state === 'succeeded' && ['FEASIBLE', 'OPTIMAL'].includes(run.solver_status ?? '');
  const chosen = usableRun ? run.candidates.find(value => value.id === candidate) : null;
  const baseline = selected?.baseline?.run_id === run?.id ? selected?.baseline : null;
  if (!capabilities.includes('generate')) return <p>Scenario Lab requires scheduling access.</p>;
  if (!data) return <section>{error ? <FormProblem error={error} /> : <p role="status">Loading saved what-ifs and the published base…</p>}<Button disabled={busy} onClick={() => perform(load)}>Reload Scenario Lab</Button></section>;
  const eventList = (items: Schema['ScenarioEventIn'][], remove?: (index: number) => void) => <ScenarioEventList events={items} employees={data.schedule.employees} skills={skills} timezone={outlet.timezone} showCosts={showCosts} onRemove={remove} />;
  return <section className="scenario-lab" aria-label="Scenario Lab workspace">
    <div className="scenario-boundary"><strong>What-if workspace</strong><p>Events here are hypothetical. Creating, running or discarding a scenario does not change real absences, availability, staffing, rules or the published schedule.</p><p>Conversion checks current real facts and creates a normal draft. Publication still needs a separate proposal and approval.</p></div>
    {fixtureMode && <p className="contract-note">Synthetic example: Wednesday absence plus Saturday evening demand. Saved scenario, event and admission fixtures are supplied; its completed run and detailed candidate fixture are not yet supplied. Unsupported preview requests remain errors.</p>}
    {notice && <p className="save-notice" role="status">{notice}</p>}
    {error && <FormProblem error={error} />}
    {needsRefresh && <p role="alert">A scenario write was not confirmed. Reload saved scenarios before another write; it has not been retried.</p>}
    <div className="scenario-saved-heading"><h2>Saved what-ifs for this week</h2><Button disabled={busy} onClick={() => perform(async signal => { await load(signal); if (selected) { const value = await client.scenario(selected.id, signal); if (!signal.aborted) update(value); } if (!signal.aborted) { setNeedsRefresh(false); setNotice('Saved scenarios reloaded. Check for the previous change before submitting it again.'); } })}>Reload saved scenarios</Button></div>
    {data.list.length ? <ul className="scenario-saved">{data.list.map(value => <li key={value.id}><div><strong>{value.title}</strong><span>{value.status}; {value.events.length} hypothetical changes. Expires {value.expires_at.slice(0, 10)}.</span></div><Button disabled={busy || !!conversion} onClick={() => perform(signal => open(value.id, signal))}>Open {value.title}</Button></li>)}</ul> : <p>No saved what-ifs for this week. Create one below.</p>}
    {!selected ? <section className="scenario-create" aria-label="Create a what-if"><h2>Explore a different week</h2><p>Starts from {data.schedule.current_version ? `published version ${data.schedule.current_version.version_number}` : 'an empty week'}. Events apply in the order below.</p><label>Scenario title<input maxLength={120} value={title} disabled={busy || needsRefresh} onChange={event => setTitle(event.target.value)} /></label>
      {eventList(events, busy ? undefined : index => setEvents(old => old.filter((_, i) => i !== index)))}
      <ScenarioEventEditor {...{ week, skills, showCosts }} timezone={outlet.timezone} employees={data.schedule.employees} disabled={busy || needsRefresh || events.length >= 20} onEvent={event => setEvents(old => [...old, event])} />
      {fixtureMode && <Button disabled={busy || needsRefresh} onClick={() => { setTitle(examples.create.title); setEvents(examples.create.events as Schema['ScenarioEventIn'][]); }}>Load Wednesday absence example</Button>}
      <Button variant="primary" disabled={busy || needsRefresh || !title.trim() || events.length > 20} onClick={() => perform(async signal => { const value = await client.createScenario(outlet.id, week, { title: title.trim(), events }, signal); if (!signal.aborted) { update(value); setTitle(''); setEvents([]); setNotice('What-if saved. Real staffing facts are unchanged.'); } }, true)}>Create what-if</Button>
    </section> : <section className="scenario-detail" aria-label="Selected what-if"><div className="review-heading"><div><h2 ref={heading} tabIndex={-1}>{selected.title}</h2><p>Status: {selected.status}. Expires {selected.expires_at.slice(0, 10)}. Times in {outlet.timezone}.</p></div><Button disabled={busy || !!conversion} onClick={() => { setSelected(null); setRun(null); setTrackedId(null); setDraft(null); setCandidate(''); setDiscard(false); }}>Close what-if</Button></div>
      <p>{selected.base_version_id === data.schedule.current_version?.id ? 'The base matches the currently loaded published week.' : selected.base_version_id == null && !data.schedule.current_version ? 'This what-if starts with an empty week.' : 'The published base differs from this what-if. Create a fresh scenario; old assumptions cannot replace the current week.'}</p>
      {eventList(selected.events)}
      {editable && !activeRun && <><ScenarioEventEditor {...{ week, skills, showCosts }} timezone={outlet.timezone} employees={data.schedule.employees} disabled={busy || selected.events.length >= 20} onEvent={event => perform(async signal => { const value = await client.addScenarioEvent(selected.id, event, signal); if (!signal.aborted) { update(value); setRun(null); setCandidate(''); setEventsChanged(true); setNotice('Hypothetical change saved. Run the scenario again to compare all current events.'); } }, true)} />
        {fixtureMode && <Button disabled={busy} onClick={() => perform(async signal => { const value = await client.addScenarioEvent(selected.id, examples.event as Schema['ScenarioEventIn'], signal); if (!signal.aborted) { update(value); setRun(null); setCandidate(''); setEventsChanged(true); } }, true)}>Add Saturday evening example</Button>}
      </>}
      {editable && <div className="scenario-run-controls"><label>Simulation priorities<select disabled={busy || !!activeRun} value={profile} onChange={event => setProfile(event.target.value as typeof profile)}>{(['balanced', 'stability', 'lowest_cost', 'fairness', 'max_coverage', 'staff_friendly'] as const).map(value => <option key={value} value={value}>{strategyName(value)}</option>)}</select></label><Button variant="primary" disabled={busy || !!activeRun || selected.base_version_id !== (data.schedule.current_version?.id ?? null)} onClick={() => perform(async signal => {
        const identity = JSON.stringify([selected.id, selected.events, profile]);
        let initial: Schema['OptimizationRun']; let attached = false;
        try { initial = await client.runScenario(selected.id, { strategy: profile, time_limit_seconds: 10 }, keyFor(identity), signal); }
        catch (value) { if (value instanceof ApiError && value.detail.code === 'run_in_progress' && typeof value.detail.details?.run_id === 'string') { attached = true; setTrackedId(value.detail.details.run_id); initial = await client.run(value.detail.details.run_id, signal); } else throw value; }
        if (signal.aborted) return;
        keys.current.delete(identity); setCandidate(''); setEventsChanged(attached); setSelected(old => old && { ...old, latest_run_id: initial.id }); await track({ ...selected, latest_run_id: initial.id }, initial, signal);
      })}>Run what-if</Button></div>}
      {trackedId && <div className="scenario-run-status"><p>Simulation run {trackedId}. {run ? runMessage(run).title : 'Status has not been confirmed.'} The real published week stays in place.</p><Button disabled={busy} onClick={() => perform(async signal => { const current = await client.scenario(selected.id, signal); if (signal.aborted) return; update(current); const value = await client.run(trackedId, signal); if (!signal.aborted) await track(current, value, signal); })}>Check simulation status</Button></div>}
      {eventsChanged && <p role="status">The event revision for these saved results is not confirmed. Run the what-if again before comparing or converting all current events.</p>}
      {run?.infeasibility && <p role="alert">{run.infeasibility.summary}</p>}{run?.error && <p role="alert">{run.error.message}</p>}
      {baseline && !eventsChanged && <section className="scenario-baseline"><h3>The original plan under these assumptions</h3><p>{baseline.hard_violations} hard violations under the what-if: {baseline.violation_codes.join(', ') || 'none reported'}. These are simulated results, not recorded published metrics.</p><dl className="decision-facts"><div><dt>Preferred coverage</dt><dd>{percent(baseline.metrics.coverage_ratio)}</dd></div><div><dt>Preferred staffing gap</dt><dd>{baseline.metrics.preferred_deficit_minutes} staff-minutes</dd></div><div><dt>Fairness burden</dt><dd>{burdenNumber(baseline.metrics.fairness_burden_deviation)}</dd></div>{showCosts && <div><dt>Estimated labour cost</dt><dd>{formatMoney(baseline.metrics.labour_cost)}</dd></div>}</dl></section>}
      {usableRun && <><PortfolioDetails portfolio={run.portfolio} showCosts={showCosts} /><ScenarioComparison run={run} baseline={baseline} showCosts={showCosts} /><fieldset className="scenario-options" disabled={busy || !editable}><legend>Choose a simulated option to review</legend>{run.candidates.map(value => <label key={value.id}><input type="radio" name="scenario-option" value={value.id} checked={candidate === value.id} onChange={() => setCandidate(value.id)} />{strategyName(value.strategy)}: {percent(value.metrics.coverage_ratio)} preferred coverage; {value.changed_shifts} changed assignments; {value.validation.hard_violations} hard violations.</label>)}</fieldset></>}
      {chosen && <section className="scenario-option-review" aria-label="Simulated option review"><h3>{strategyName(chosen.strategy)} under the what-if</h3><p>All explanations and deltas below use hypothetical facts. The original plan is evaluated under the same assumptions.</p><FairnessBreakdown metrics={chosen.metrics} /><DecisionEvidence trace={chosen.trace} explanations={chosen.explanations} employees={data.schedule.employees} showCosts={showCosts} assignments={data.schedule.current_version?.shifts} skills={skills} timezone={outlet.timezone} /><p>Turn this into a plan revalidates current real facts. Hypothetical absences, demand, closures, caps and rules are never saved as real facts. The resulting draft still needs proposal approval.</p>{canConvert ? <Button variant="primary" disabled={busy || !editable || chosen.validation.hard_violations > 0} onClick={() => perform(async signal => { const pending = { scenario: selected.id, candidate: chosen.id, key: keyFor(`convert:${selected.id}:${run!.id}:${chosen.id}`) }; setConversion(pending); const value = await convert(pending, signal); if (!signal.aborted) { if (value.source !== 'scenario' || value.status !== 'draft' || value.schedule_id !== selected.schedule_id) throw new Error('Conversion did not confirm a scenario draft for this schedule. Check the saved scenario.'); setDraft(value); setConversion(null); update({ ...selected, status: 'converted', converted_version_id: value.id }); setNotice('Scenario converted to a draft. No hypothetical facts were saved; nothing is published.'); } })}>Turn this into a plan</Button> : <p>A manager with publication permission must convert this option.</p>}</section>}
      {conversion && !draft && <section className="surface-note"><p>Conversion has not been confirmed. Check the scenario or explicitly retry the same conversion key; no other option can be converted while this request is unresolved.</p><Button disabled={busy} onClick={() => perform(async signal => { const value = await client.scenario(conversion.scenario, signal); if (signal.aborted) return; update(value); if (value.converted_version_id) { const result = await client.version(value.converted_version_id, signal); if (!signal.aborted) { openConvertedRead(result); setConversion(null); } } else if (value.status !== 'open') setConversion(null); })}>Check conversion result</Button><Button disabled={busy} onClick={() => perform(async signal => { const value = await convert(conversion, signal); if (!signal.aborted) { setDraft(value); setConversion(null); update({ ...selected, status: 'converted', converted_version_id: value.id }); } })}>Retry same conversion</Button></section>}
      {selected.converted_version_id && !draft && <Button disabled={busy} onClick={() => perform(async signal => { const value = await client.version(selected.converted_version_id!, signal); if (!signal.aborted) openConvertedRead(value); })}>Open converted draft</Button>}
      {draft && <section aria-label="Scenario draft review"><h3>Converted draft {draft.version_number}</h3><p>Review current-fact metrics before publication.</p><ProposalReview {...{ client, draft, fixtureMode, showCosts }} timezone={outlet.timezone} onReload={() => perform(load)} onPublished={() => { setNotice('Publication confirmed by the server. The scenario remains separate from real staffing facts.'); setDraft(null); perform(load); }} /></section>}
      {editable && !activeRun && <div className="scenario-discard">{discard ? <><p>Discard this hypothetical workspace? Saved real staffing facts and published assignments stay in place.</p><Button disabled={busy} onClick={() => perform(async signal => { const value = await client.discardScenario(selected.id, signal); if (!signal.aborted) { update(value); setDiscard(false); setCandidate(''); setNotice('What-if discarded. Real staffing facts are unchanged.'); } }, true)}>Confirm discard what-if</Button><Button disabled={busy} onClick={() => setDiscard(false)}>Keep what-if</Button></> : <Button disabled={busy} onClick={() => setDiscard(true)}>Discard what-if</Button>}</div>}
    </section>}
  </section>;
}

function ScenarioComparison({ run, baseline, showCosts }: { run: Schema['OptimizationRun']; baseline: Schema['ScenarioBaseline'] | null | undefined; showCosts: boolean }) {
  const rows = [{ label: 'Preferred coverage', value: (m: Schema['Metrics']) => percent(m.coverage_ratio) }, { label: 'Minimum shortfall', value: (m: Schema['Metrics']) => `${m.minimum_deficit_minutes} staff-minutes` }, { label: 'Preferred staffing gap', value: (m: Schema['Metrics']) => `${m.preferred_deficit_minutes} staff-minutes` }, { label: 'Overtime', value: (m: Schema['Metrics']) => `${m.overtime_minutes} min` }, { label: 'Fairness burden', value: (m: Schema['Metrics']) => burdenNumber(m.fairness_burden_deviation) }, ...(showCosts ? [{ label: 'Estimated labour cost', value: (m: Schema['Metrics']) => formatMoney(m.labour_cost) }] : [])];
  return <div className="review-table-scroll" role="region" aria-label="What-if comparison" tabIndex={0}><table><caption>All values are evaluated under the scenario assumptions. The baseline belongs to this simulation run; recorded published scores are not substituted.</caption><thead><tr><th scope="col">Measure</th><th scope="col">Original plan under assumptions</th>{run.candidates.map(value => <th scope="col" key={value.id}>{strategyName(value.strategy)}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.label}><th scope="row">{row.label}</th><td>{baseline ? row.value(baseline.metrics) : 'Matching simulated baseline not reported'}</td>{run.candidates.map(value => <td key={value.id}>{row.value(value.metrics)}</td>)}</tr>)}</tbody></table></div>;
}
