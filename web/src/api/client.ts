import type { ApiErrorBody, Persona, Scenario, Schema } from './types';

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly detail: ApiErrorBody) {
    super(detail.message); this.name = 'ApiError';
  }
}

export type ClientOptions = {
  baseUrl: string;
  fetcher?: typeof fetch;
  onUnauthorized?: () => void;
  fixtureScenario?: Scenario;
};

/** Session credentials exist only in this instance; never persisted to browser storage. */
export class SchedulingClient {
  private token: string | null = null;
  private generation = 0;
  private fetcher: typeof fetch;
  constructor(private readonly options: ClientOptions) { this.fetcher = options.fetcher ?? ((input, init) => fetch(input, init)); }

  clearSession() { this.token = null; this.generation += 1; }
  setFixtureScenario(scenario: Scenario) { this.options.fixtureScenario = scenario; }

  private async request<T>(path: string, init: RequestInit = {}, idempotencyKey?: string): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (init.body) headers.set('Content-Type', 'application/json');
    if (this.token) headers.set('Authorization', `Bearer ${this.token}`);
    if (idempotencyKey) headers.set('Idempotency-Key', idempotencyKey);
    // Scenario headers are strictly confined to the same-origin fixture gateway.
    if (this.options.baseUrl === '/api/fixture' && this.options.fixtureScenario) headers.set('X-ShiftPilot-Scenario', this.options.fixtureScenario);
    const response = await this.fetcher(`${this.options.baseUrl.replace(/\/$/, '')}${path}`, { ...init, headers, cache: 'no-store', credentials: 'omit' });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = isErrorEnvelope(payload) ? payload.error : { code: 'internal' as const, message: 'The scheduling service returned an unreadable response.', retryable: false, details: {} };
      if (response.status === 401) { this.clearSession(); this.options.onUnauthorized?.(); }
      throw new ApiError(response.status, detail);
    }
    if (payload === null) throw new ApiError(response.status, { code: 'internal', message: 'The scheduling service returned an empty response.', retryable: false, details: {} });
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
  generate(outletId: string, week: string, input: Schema['GenerateRequest'], idempotencyKey: string, signal?: AbortSignal) {
    if (!idempotencyKey) throw new Error('Generation requires a stable idempotency key.');
    return this.request<Schema['OptimizationRun']>(`/v2/outlets/${encodeURIComponent(outletId)}/schedules/${encodeURIComponent(week)}/generate`, { method: 'POST', body: JSON.stringify(input), signal }, idempotencyKey);
  }
  run(runId: string, signal?: AbortSignal) { return this.request<Schema['OptimizationRun']>(`/v2/optimization-runs/${encodeURIComponent(runId)}`, { signal }); }
  version(versionId: string, signal?: AbortSignal) { return this.request<Schema['ScheduleVersion']>(`/v2/schedule-versions/${encodeURIComponent(versionId)}`, { signal }); }
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
