import type { Persona, Scenario, Schema } from './types';

type Preview = { touched: number; employees: Schema['Employee'][]; availability: Map<string, Schema['Availability']>; demand: Map<string, Schema['StaffingRequirements']>; creates: Map<string, { body: string; employee: Schema['Employee'] }>; templates?: Schema['StaffingTemplateSet']; expansions: Map<string, { fingerprint: string; value: Schema['StaffingRequirements'] }> };
const sessions = new Map<string, Preview>();
const respond = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'synthetic-session-edit' } });
const failure = (code: Schema['ErrorBody']['code'], message: string, status: number, details: Record<string, unknown> = {}) => respond({ error: { code, message, retryable: false, details } }, status);

/** Volatile UI demo state only. No real API forwarding, database access or roster computation. */
export async function managementFixture(url: URL, request: Request, persona: Persona, scenario: Scenario | null, fixture: <T>(name: string) => T): Promise<Response | null> {
  const previewId = request.headers.get('X-ShiftPilot-Preview-Session');
  const employeePath = /^\/v2\/employees(?:\/([^/]+)(\/availability)?)?$/.exec(url.pathname);
  const demandPath = /^\/v2\/outlets\/([^/]+)\/staffing-requirements$/.exec(url.pathname);
  const templatePath = /^\/v2\/outlets\/([^/]+)\/staffing-templates$/.exec(url.pathname);
  const expandPath = /^\/v2\/outlets\/([^/]+)\/staffing-requirements\/expand$/.exec(url.pathname);
  if (!previewId || !employeePath && !demandPath && !templatePath && !expandPath) return null;
  if (!/^[\w-]{1,80}$/.test(previewId)) return failure('validation_failed', 'Invalid preview session.', 422);
  if (persona === 'staff' || scenario === 'denied') return failure('permission_denied', 'This resource is outside your access.', 403);
  const now = Date.now();
  for (const [key, value] of sessions) if (now - value.touched > 30 * 60000) sessions.delete(key);
  const key = `${persona}:${previewId}`;
  let state = sessions.get(key);
  if (!state) {
    if (sessions.size >= 64) sessions.delete(sessions.keys().next().value!);
    state = { touched: now, employees: ['employees.list', 'employees.list.owner.koramangala', 'employees.list.owner.hsr'].flatMap(name => fixture<Schema['EmployeeList']>(name).items), availability: new Map(['availability.get', 'availability.get.student'].map(name => { const value = fixture<Schema['Availability']>(name); return [value.employee_id, value]; })), demand: new Map(), creates: new Map(), expansions: new Map() };
    sessions.set(key, state);
  }
  state.touched = now;
  const managerOutlet = fixture<Schema['Me']>('me.manager').outlet_id;
  const outlets = fixture<Schema['OutletList']>('outlets.owner').items;
  const allowedOutlet = (id: string) => outlets.some(outlet => outlet.id === id) && (persona === 'owner' || id === managerOutlet);
  const employee = employeePath?.[1] ? state.employees.find(item => item.id === employeePath[1]) : null;
  if (employeePath?.[1] && (!employee || !allowedOutlet(employee.home_outlet_id))) return failure('permission_denied', 'This employee is outside your access.', 403);
  if (templatePath || expandPath) {
    const outletId = templatePath?.[1] ?? expandPath![1];
    if (!allowedOutlet(outletId)) return failure('permission_denied', 'This outlet is outside your access.', 403);
    const initial = fixture<Schema['StaffingTemplateSet']>('staffing_templates.list');
    if (outletId !== initial.outlet_id) return failure('not_implemented', 'No weekly template fixture is supplied for this outlet.', 501);
    state.templates ??= initial;
    if (templatePath && request.method === 'GET') return respond(state.templates);
  }
  if (request.method === 'GET') {
    if (employeePath && !employeePath[1]) {
      const outletId = url.searchParams.get('outlet_id') ?? '';
      if (!allowedOutlet(outletId)) return failure('permission_denied', 'This outlet is outside your access.', 403);
      return respond({ items: state.employees.filter(item => item.home_outlet_id === outletId), next_cursor: null });
    }
    if (employee && employeePath?.[2]) return respond(state.availability.get(employee.id) ?? { employee_id: employee.id, windows: [], revision: 1 });
    if (employee) return respond(employee);
    if (demandPath) {
      if (!allowedOutlet(demandPath[1])) return failure('permission_denied', 'This outlet is outside your access.', 403);
      const week = url.searchParams.get('week_start') ?? '';
      const initial = fixture<Schema['StaffingRequirements']>('staffing.get');
      const stored = state.demand.get(`${demandPath[1]}:${week}`);
      if (stored) return respond(stored);
      if (demandPath[1] === initial.outlet_id && week === initial.week_start) return respond(initial);
      return failure('not_implemented', 'No staffing fixture is available for this outlet and week.', 501);
    }
    return null;
  }
  if (scenario === 'stale') return failure('stale_version', 'These values were changed by someone else. Reload before saving.', 409);
  if (Number(request.headers.get('Content-Length')) > 2000000) return failure('validation_failed', 'Preview request is too large.', 422);
  const input = await request.json().catch(() => null);
  if (!input || typeof input !== 'object' || Array.isArray(input)) return failure('validation_failed', 'Send a valid form.', 422);
  if (templatePath && request.method === 'PUT') {
    if (input.base_revision !== state.templates!.revision) return failure('stale_version', 'The weekly template changed. Reload before saving.', 409);
    const supplied = fixture<Schema['StaffingTemplateSet']>('staffing_templates.put');
    if (state.templates!.revision !== 1 || JSON.stringify(input.items) !== JSON.stringify(supplied.items)) return failure('not_implemented', 'The supplied template-save example increases Saturday Grill staffing. Other changes need a connected API.', 501);
    state.templates = supplied; return respond(supplied);
  }
  if (expandPath && request.method === 'POST') {
    const idempotencyKey = request.headers.get('Idempotency-Key');
    if (!idempotencyKey) return failure('validation_failed', 'An expansion key is required.', 422);
    const week = url.searchParams.get('week_start') ?? '';
    const fingerprint = JSON.stringify([expandPath[1], week, input]);
    const replay = state.expansions.get(idempotencyKey);
    if (replay) return replay.fingerprint === fingerprint ? respond(replay.value) : failure('idempotency_conflict', 'This expansion key belongs to another request.', 409);
    const initial = fixture<Schema['StaffingRequirements']>('staffing.get');
    const current = state.demand.get(`${expandPath[1]}:${week}`) ?? initial;
    if (input.base_demand_revision !== current.demand_revision) return failure('stale_version', 'Dated staffing changed. Reload it before expanding.', 409);
    if (week !== initial.week_start || state.templates!.revision !== 1 || input.use_demand_bands !== false || input.base_demand_revision !== initial.demand_revision || JSON.stringify(current.intervals) !== JSON.stringify(initial.intervals)) return failure('not_implemented', 'Expansion fixtures cover the original weekly template without bands or manual changes. A changed template or dated week needs a connected API.', 501);
    const value = fixture<Schema['StaffingRequirements']>('staffing.expand');
    state.demand.set(`${expandPath[1]}:${week}`, value);
    if (state.expansions.size >= 64) state.expansions.delete(state.expansions.keys().next().value!);
    state.expansions.set(idempotencyKey, { fingerprint, value }); return respond(value);
  }
  if (employeePath && !employeePath[1] && request.method === 'POST') {
    const idempotencyKey = request.headers.get('Idempotency-Key');
    if (!idempotencyKey) return failure('validation_failed', 'An idempotency key is required.', 422);
    const body = JSON.stringify(input), previous = state.creates.get(idempotencyKey);
    if (previous) return previous.body === body ? respond(previous.employee, 201) : failure('idempotency_conflict', 'This key was used for another request.', 409);
    if (!allowedOutlet(input.home_outlet_id)) return failure('permission_denied', 'This outlet is outside your access.', 403);
    if (state.employees.length >= 200 || typeof input.name !== 'string' || !input.name.trim()) return failure('validation_failed', 'Enter a name. Preview capacity is 200 employees.', 422);
    const value: Schema['Employee'] = { ...input, id: crypto.randomUUID(), revision: 1 };
    state.employees.push(value); state.creates.set(idempotencyKey, { body, employee: value });
    return respond(value, 201);
  }
  if (employee && !employeePath?.[2] && request.method === 'PATCH') {
    if (input.base_revision !== employee.revision) return failure('stale_version', 'Employee details have changed.', 409, { current_revision: employee.revision });
    if (input.home_outlet_id && !allowedOutlet(input.home_outlet_id)) return failure('permission_denied', 'This outlet is outside your access.', 403);
    const changes = Object.fromEntries(Object.entries(input).filter(([field]) => field in employee && !['id', 'revision'].includes(field)));
    const value = { ...employee, ...changes, revision: employee.revision + 1 } as Schema['Employee'];
    state.employees = state.employees.map(item => item.id === value.id ? value : item);
    return respond(value);
  }
  if (employee && employeePath?.[2] && request.method === 'PUT') {
    const current = state.availability.get(employee.id) ?? { employee_id: employee.id, revision: 1, windows: [] };
    if (input.base_revision !== current.revision) return failure('stale_version', 'Availability has changed.', 409, { current_revision: current.revision });
    if (!Array.isArray(input.windows) || input.windows.length > 200) return failure('validation_failed', 'Send at most 200 recurring windows.', 422);
    const value = { employee_id: employee.id, windows: input.windows, revision: current.revision + 1 };
    state.availability.set(employee.id, value); return respond(value);
  }
  if (demandPath && request.method === 'PUT') {
    if (!allowedOutlet(demandPath[1])) return failure('permission_denied', 'This outlet is outside your access.', 403);
    const week = url.searchParams.get('week_start') ?? '';
    const initial = fixture<Schema['StaffingRequirements']>('staffing.get');
    const current = state.demand.get(`${demandPath[1]}:${week}`) ?? (demandPath[1] === initial.outlet_id && week === initial.week_start ? initial : null);
    if (!current) return failure('not_implemented', 'No staffing fixture is available for this outlet and week.', 501);
    if (input.base_demand_revision !== current.demand_revision) return failure('stale_version', 'Staffing needs have changed.', 409, { current_demand_revision: current.demand_revision });
    if (!Array.isArray(input.intervals) || input.intervals.length === 0 || input.intervals.length > 5000) return failure('validation_failed', 'Send between 1 and 5000 intervals.', 422);
    const value = { ...current, intervals: input.intervals, demand_revision: current.demand_revision + 1 };
    state.demand.set(`${demandPath[1]}:${week}`, value); return respond(value);
  }
  return null;
}
