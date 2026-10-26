import type { ApiErrorBody, Persona, Scenario, Schema } from './types';
import { QueryClient } from '@tanstack/react-query';

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly detail: ApiErrorBody, public readonly retryAfter: string | null = null) {
    super(detail.message); this.name = 'ApiError';
  }
}

export type ClientOptions = {
  baseUrl: string;
  fetcher?: typeof fetch;
  onUnauthorized?: () => void;
  fixtureScenario?: Scenario;
  fixtureApprovalOutcome?: 'published' | 'changed' | 'stale' | 'invalid';
};

/** Session credentials exist only in this instance; never persisted to browser storage. */
export class SchedulingClient {
  readonly queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 300000 } } });
  private token: string | null = null;
  private generation = 0;
  private expired: { generation: number; error: ApiError } | null = null;
  private previewSession = crypto.randomUUID();
  private readonly reads = new Map<string, { etag: string; payload: unknown }>();
  private fetcher: typeof fetch;
  constructor(private readonly options: ClientOptions) { this.fetcher = options.fetcher ?? ((input, init) => fetch(input, init)); }

  clearSession() { this.token = null; this.generation += 1; this.previewSession = crypto.randomUUID(); this.reads.clear(); this.queryClient.clear(); }
  setFixtureScenario(scenario: Scenario) { this.options.fixtureScenario = scenario; }
  setFixtureApprovalOutcome(outcome: NonNullable<ClientOptions['fixtureApprovalOutcome']>) { this.options.fixtureApprovalOutcome = outcome; }

  private async request<T>(path: string, init: RequestInit = {}, idempotencyKey?: string): Promise<T> {
    if ((init.method ?? 'GET') !== 'GET') return this.transport<T>(path, init, idempotencyKey);
    const generation = this.generation;
    try {
      init.signal?.throwIfAborted();
      // A shared GET belongs to the session. A departing screen cancels its own
      // wait, while another screen can still consume the same in-flight read.
      const read = this.queryClient.fetchQuery({ queryKey: ['session', generation, path], queryFn: ({ signal }) => this.transport<T>(path, { ...init, signal }) });
      return await waitForRead(read, init.signal);
    }
    catch (error) {
      if (this.expired?.generation === generation) throw this.expired.error;
      if (generation !== this.generation) throw new DOMException('Session was replaced', 'AbortError');
      throw error;
    }
  }

  private async transport<T>(path: string, init: RequestInit = {}, idempotencyKey?: string): Promise<T> {
    const generation = this.generation;
    const cacheable = (init.method ?? 'GET') === 'GET' && (/^\/v2\/outlets\/[^/]+\/schedules\/[^/]+$/.test(path) || path.startsWith('/v2/schedule-versions/'));
    const cached = cacheable ? this.reads.get(path) : undefined;
    const headers = new Headers(init.headers);
    if (cached) headers.set('If-None-Match', cached.etag);
    headers.set('Accept', 'application/json');
    if (init.body) headers.set('Content-Type', 'application/json');
    if (this.token) headers.set('Authorization', `Bearer ${this.token}`);
    if (idempotencyKey) headers.set('Idempotency-Key', idempotencyKey);
    // Scenario headers are strictly confined to the same-origin fixture gateway.
    if (this.options.baseUrl === '/api/fixture' && this.options.fixtureScenario) headers.set('X-ShiftPilot-Scenario', this.options.fixtureScenario);
    if (this.options.baseUrl === '/api/fixture') headers.set('X-ShiftPilot-Preview-Session', this.previewSession);
    if (this.options.baseUrl === '/api/fixture' && this.options.fixtureApprovalOutcome) headers.set('X-ShiftPilot-Approval-Outcome', this.options.fixtureApprovalOutcome);
    const response = await this.fetcher(`${this.options.baseUrl.replace(/\/$/, '')}${path}`, { ...init, headers, cache: 'no-store', credentials: 'omit' });
    if (generation !== this.generation || init.signal?.aborted) throw new DOMException('Session was replaced', 'AbortError');
    if (response.status === 304 && cached) return structuredClone(cached.payload) as T;
    const payload: unknown = await response.json().catch(() => null);
    if (generation !== this.generation || init.signal?.aborted) throw new DOMException('Session was replaced', 'AbortError');
    if (!response.ok) {
      const detail = isErrorEnvelope(payload) ? payload.error : { code: 'internal' as const, message: 'The scheduling service returned an unreadable response.', retryable: false, details: {} };
      if (response.status === 401) { this.expired = { generation, error: new ApiError(response.status, detail) }; this.clearSession(); this.options.onUnauthorized?.(); }
      throw new ApiError(response.status, detail, response.headers.get('Retry-After'));
    }
    if (payload === null) throw new ApiError(response.status, { code: 'internal', message: 'The scheduling service returned an empty response.', retryable: false, details: {} });
    if ((init.method ?? 'GET') !== 'GET') { this.reads.clear(); await this.queryClient.invalidateQueries({ refetchType: 'none' }); }
    const etag = response.headers.get('ETag');
    if (cacheable && etag && generation === this.generation) this.reads.set(path, { etag, payload: structuredClone(payload) });
    return payload as T;
  }

  async signIn(persona: Persona, signal?: AbortSignal) {
    this.clearSession();
    const generation = this.generation;
    const session = await this.request<Schema['DemoSession']>('/v2/session/demo', { method: 'POST', body: JSON.stringify({ persona }), signal });
    if (generation !== this.generation || signal?.aborted) throw new DOMException('Session was replaced', 'AbortError');
    this.token = session.access_token;
    return session.me;
  }
  me(signal?: AbortSignal) { return this.request<Schema['Me']>('/v2/me', { signal }); }
  rules(includeArchived: boolean, signal?: AbortSignal) { return this.request<Schema['RuleList']>(`/v2/rules?include_archived=${includeArchived}`, { signal }); }
  previewRule(input: Schema['RuleDefinition'], signal?: AbortSignal) { return this.request<Schema['RulePreview']>('/v2/rules/preview', { method: 'POST', body: JSON.stringify(input), signal }); }
  createRule(input: Schema['RuleDefinition'], key: string, signal?: AbortSignal) { return this.request<Schema['SchedulingRule']>('/v2/rules', { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  archiveRule(id: string, signal?: AbortSignal) { return this.request<Schema['SchedulingRule']>(`/v2/rules/${encodeURIComponent(id)}/archive`, { method: 'POST', signal }); }
  scenarios(outletId: string, week: string, signal?: AbortSignal) { return this.request<Schema['ScenarioList']>(`/v2/outlets/${encodeURIComponent(outletId)}/scenarios?week_start=${encodeURIComponent(week)}`, { signal }); }
  scenario(id: string, signal?: AbortSignal) { return this.request<Schema['Scenario']>(`/v2/scenarios/${encodeURIComponent(id)}`, { signal }); }
  createScenario(outletId: string, week: string, input: Schema['CreateScenarioRequest'], signal?: AbortSignal) { return this.request<Schema['Scenario']>(`/v2/outlets/${encodeURIComponent(outletId)}/schedules/${encodeURIComponent(week)}/scenarios`, { method: 'POST', body: JSON.stringify(input), signal }); }
  addScenarioEvent(id: string, input: Schema['ScenarioEventIn'], signal?: AbortSignal) { return this.request<Schema['Scenario']>(`/v2/scenarios/${encodeURIComponent(id)}/events`, { method: 'POST', body: JSON.stringify(input), signal }); }
  runScenario(id: string, input: Schema['ScenarioRunRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['OptimizationRun']>(`/v2/scenarios/${encodeURIComponent(id)}/run`, { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  convertScenario(id: string, input: Schema['ConvertScenarioRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['ScheduleVersion']>(`/v2/scenarios/${encodeURIComponent(id)}/convert`, { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  discardScenario(id: string, signal?: AbortSignal) { return this.request<Schema['Scenario']>(`/v2/scenarios/${encodeURIComponent(id)}/discard`, { method: 'POST', signal }); }
  recommendReplacements(input: Schema['ReplacementRequest'], signal?: AbortSignal) { return this.request<Schema['ReplacementRecommendations']>('/v2/recommendations/replacements', { method: 'POST', body: JSON.stringify(input), signal }); }
  absences(outletId: string, from: string, to: string, signal?: AbortSignal) { return this.request<Schema['AbsenceList']>(`/v2/absences?${new URLSearchParams({ outlet_id: outletId, from, to })}`, { signal }); }
  reportAbsence(input: Schema['ReportAbsenceRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['AbsenceReport']>('/v2/absences', { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  updateAbsence(id: string, input: Schema['UpdateAbsenceRequest'], signal?: AbortSignal) { return this.request<Schema['AbsenceReport']>(`/v2/absences/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(input), signal }); }
  repair(outletId: string, week: string, input: Schema['RepairRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['OptimizationRun']>(`/v2/outlets/${encodeURIComponent(outletId)}/schedules/${encodeURIComponent(week)}/repair`, { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  outlets(signal?: AbortSignal) { return this.request<Schema['OutletList']>('/v2/outlets', { signal }); }
  skills(signal?: AbortSignal) { return this.request<Schema['SkillList']>('/v2/skills', { signal }); }
  schedule(outletId: string, week: string, signal?: AbortSignal) {
    return this.request<Schema['ScheduleWeek']>(`/v2/outlets/${encodeURIComponent(outletId)}/schedules/${encodeURIComponent(week)}`, { signal });
  }
  myWeek(week: string, signal?: AbortSignal) { return this.request<Schema['MyWeek']>(`/v2/me/shifts?week_start=${encodeURIComponent(week)}`, { signal }); }
  employees(outletId: string, cursor?: string, signal?: AbortSignal) {
    const query = new URLSearchParams({ outlet_id: outletId });
    if (cursor) query.set('cursor', cursor);
    return this.request<Schema['EmployeeList']>(`/v2/employees?${query}`, { signal });
  }
  availability(employeeId: string, signal?: AbortSignal) { return this.request<Schema['Availability']>(`/v2/employees/${encodeURIComponent(employeeId)}/availability`, { signal }); }
  employee(employeeId: string, signal?: AbortSignal) { return this.request<Schema['Employee']>(`/v2/employees/${encodeURIComponent(employeeId)}`, { signal }); }
  createEmployee(input: Schema['EmployeeCreate'], key: string, signal?: AbortSignal) {
    if (!key) throw new Error('Creating an employee requires an idempotency key.');
    return this.request<Schema['Employee']>('/v2/employees', { method: 'POST', body: JSON.stringify(input), signal }, key);
  }
  updateEmployee(id: string, input: Schema['EmployeeUpdate'], signal?: AbortSignal) { return this.request<Schema['Employee']>(`/v2/employees/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(input), signal }, crypto.randomUUID()); }
  saveAvailability(id: string, input: Schema['AvailabilityUpdate'], signal?: AbortSignal) { return this.request<Schema['Availability']>(`/v2/employees/${encodeURIComponent(id)}/availability`, { method: 'PUT', body: JSON.stringify(input), signal }, crypto.randomUUID()); }
  staffing(outletId: string, week: string, signal?: AbortSignal) { return this.request<Schema['StaffingRequirements']>(`/v2/outlets/${encodeURIComponent(outletId)}/staffing-requirements?week_start=${encodeURIComponent(week)}`, { signal }); }
  staffingTemplates(outletId: string, signal?: AbortSignal) { return this.request<Schema['StaffingTemplateSet']>(`/v2/outlets/${encodeURIComponent(outletId)}/staffing-templates`, { signal }); }
  saveStaffingTemplates(outletId: string, input: Schema['StaffingTemplateUpdate'], signal?: AbortSignal) { return this.request<Schema['StaffingTemplateSet']>(`/v2/outlets/${encodeURIComponent(outletId)}/staffing-templates`, { method: 'PUT', body: JSON.stringify(input), signal }); }
  expandStaffing(outletId: string, week: string, input: Schema['ExpandStaffingRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['StaffingRequirements']>(`/v2/outlets/${encodeURIComponent(outletId)}/staffing-requirements/expand?week_start=${encodeURIComponent(week)}`, { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  saveStaffing(outletId: string, week: string, input: Schema['StaffingRequirementsUpdate'], signal?: AbortSignal) { return this.request<Schema['StaffingRequirements']>(`/v2/outlets/${encodeURIComponent(outletId)}/staffing-requirements?week_start=${encodeURIComponent(week)}`, { method: 'PUT', body: JSON.stringify(input), signal }, crypto.randomUUID()); }
  generate(outletId: string, week: string, input: Schema['GenerateRequest'], idempotencyKey: string, signal?: AbortSignal) {
    if (!idempotencyKey) throw new Error('Generation requires a stable idempotency key.');
    return this.request<Schema['OptimizationRun']>(`/v2/outlets/${encodeURIComponent(outletId)}/schedules/${encodeURIComponent(week)}/generate`, { method: 'POST', body: JSON.stringify(input), signal }, idempotencyKey);
  }
  run(runId: string, signal?: AbortSignal) { return this.request<Schema['OptimizationRun']>(`/v2/optimization-runs/${encodeURIComponent(runId)}`, { signal }); }
  candidate(id: string, signal?: AbortSignal) { return this.request<Schema['CandidateDetail']>(`/v2/optimization-candidates/${encodeURIComponent(id)}`, { signal }); }
  selectCandidate(id: string, key: string, signal?: AbortSignal) { return this.request<Schema['ScheduleVersion']>(`/v2/optimization-candidates/${encodeURIComponent(id)}/select`, { method: 'POST', signal }, requiredKey(key)); }
  createProposal(input: Schema['CreateProposalRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['Proposal']>('/v2/proposals', { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  proposal(id: string, signal?: AbortSignal) { return this.request<Schema['Proposal']>(`/v2/proposals/${encodeURIComponent(id)}`, { signal }); }
  approveProposal(id: string, input: Schema['ApproveProposalRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['ProposalDecision']>(`/v2/proposals/${encodeURIComponent(id)}/approve`, { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  rejectProposal(id: string, key: string, signal?: AbortSignal) { return this.request<Schema['Proposal']>(`/v2/proposals/${encodeURIComponent(id)}/reject`, { method: 'POST', signal }, requiredKey(key)); }
  version(versionId: string, signal?: AbortSignal) { return this.request<Schema['ScheduleVersion']>(`/v2/schedule-versions/${encodeURIComponent(versionId)}`, { signal }); }
  versions(scheduleId: string, signal?: AbortSignal) { return this.request<Schema['VersionHistory']>(`/v2/schedules/${encodeURIComponent(scheduleId)}/versions`, { signal }); }
  compareVersions(toId: string, fromId: string, signal?: AbortSignal) { return this.request<Schema['VersionDiff']>(`/v2/schedule-versions/${encodeURIComponent(toId)}/compare?with=${encodeURIComponent(fromId)}`, { signal }); }
  restoreVersion(id: string, input: Schema['RestoreRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['ScheduleVersion']>(`/v2/schedule-versions/${encodeURIComponent(id)}/restore`, { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
  proposals(scheduleId: string, signal?: AbortSignal) { return this.request<Schema['ProposalList']>(`/v2/proposals?schedule_id=${encodeURIComponent(scheduleId)}&status=pending`, { signal }); }
  createDraft(outletId: string, week: string, input: Schema['CreateDraftRequest'], key: string, signal?: AbortSignal, previewExample?: 'cover') { return this.request<Schema['ScheduleVersion']>(`/v2/outlets/${encodeURIComponent(outletId)}/schedules/${encodeURIComponent(week)}/drafts`, { method: 'POST', body: JSON.stringify(input), signal, ...(this.options.baseUrl === '/api/fixture' && previewExample === 'cover' ? { headers: { 'X-ShiftPilot-Draft-Example': 'cover' } } : {}) }, requiredKey(key)); }
  previewEdits(id: string, input: Schema['EditRequest'], signal?: AbortSignal) { return this.request<Schema['EditPreview']>(`/v2/schedule-versions/${encodeURIComponent(id)}/edits/preview`, { method: 'POST', body: JSON.stringify(input), signal }); }
  // Client recovery remains conservative: reload after an uncertain save; never retry automatically.
  applyEdits(id: string, input: Schema['EditRequest'], key: string, signal?: AbortSignal) { return this.request<Schema['ScheduleVersion']>(`/v2/schedule-versions/${encodeURIComponent(id)}/edits`, { method: 'POST', body: JSON.stringify(input), signal }, requiredKey(key)); }
}

function requiredKey(key: string) { if (!key) throw new Error('This action requires a stable idempotency key.'); return key; }

function waitForRead<T>(read: Promise<T>, signal?: AbortSignal | null): Promise<T> {
  if (!signal) return read;
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason ?? new DOMException('Aborted', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
    read.then(value => { signal.removeEventListener('abort', abort); resolve(value); }, error => { signal.removeEventListener('abort', abort); reject(error); });
    if (signal.aborted) abort();
  });
}

function isErrorEnvelope(value: unknown): value is { error: ApiErrorBody } {
  if (!value || typeof value !== 'object' || !('error' in value)) return false;
  const error = value.error;
  return !!error && typeof error === 'object' && 'code' in error && typeof error.code === 'string' && 'message' in error && typeof error.message === 'string' && 'retryable' in error && typeof error.retryable === 'boolean';
}

/** Polling is read-only, cancellable and bounded; generation POSTs are never retried here. */
export async function watchRun(client: SchedulingClient, initial: Schema['OptimizationRun'], options: { signal: AbortSignal; onUpdate: (run: Schema['OptimizationRun']) => void; maxPolls?: number; wait?: (ms: number, signal: AbortSignal) => Promise<void> }) {
  let run = initial;
  const wait = options.wait ?? abortableDelay;
  for (let i = 0; i < (options.maxPolls ?? 60); i += 1) {
    options.signal.throwIfAborted();
    options.onUpdate(run);
    if (!['queued', 'running'].includes(run.job_state)) return run;
    if (run.poll_after_ms === null) throw new Error('The active run did not provide polling guidance.');
    await wait(Math.max(100, Math.min(run.poll_after_ms, 10000)), options.signal);
    run = await client.run(run.id, options.signal);
  }
  options.onUpdate(run);
  throw new Error('Status checks paused. The optimizer may still be running; use its run ID to check again.');
}

export function abortableDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const abort = () => { clearTimeout(timer); reject(signal.reason ?? new DOMException('Aborted', 'AbortError')); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
    signal.addEventListener('abort', abort, { once: true });
  });
}

/** Attach to an admitted run without resubmitting a write. */
export async function generateOrAttach(client: SchedulingClient, outletId: string, week: string, input: Schema['GenerateRequest'], key: string, signal: AbortSignal) {
  try { return await client.generate(outletId, week, input, key, signal); }
  catch (error) {
    if (error instanceof ApiError && error.detail.code === 'run_in_progress' && typeof error.detail.details?.run_id === 'string') return client.run(error.detail.details.run_id, signal);
    throw error;
  }
}
