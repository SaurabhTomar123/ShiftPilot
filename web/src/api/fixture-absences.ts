import records from './generated/fixtures.json';
import type { Fixture, Schema } from './types';

const fixtures = records as unknown as Record<string, Fixture>;
const reply = (name: string) => { const response = fixtures[name].response; return Response.json(response.body, { status: response.status, headers: { 'Cache-Control': 'no-store', 'X-ShiftPilot-Source': 'contract-fixture' } }); };
const unsupported = () => Response.json({ error: { code: 'not_implemented', message: 'This absence or repair request has no matching provider fixture. Use the live API to save other dates, change statuses, or review a detailed repair option.', retryable: false, details: {} } }, { status: 501 });

/** Replay supplied provider facts only. Never fabricate a successful repair or a saved absence. */
export async function absenceFixture(url: URL, request: Request): Promise<Response | null> {
  const repair = fixtures['repair.accepted'].request.path_params!;
  const accepted = fixtures['repair.accepted'].response.body as Schema['OptimizationRun'];
  const isAbsence = url.pathname === '/v2/absences' || url.pathname.startsWith('/v2/absences/');
  const isRepair = /^\/v2\/outlets\/[^/]+\/schedules\/[^/]+\/repair$/.test(url.pathname);
  const repairResult = fixtures['run.repair.widened'].response.body as Schema['OptimizationRun'];
  const isRepairRead = url.pathname === `/v2/optimization-runs/${accepted.id}` || repairResult.candidates.some(candidate => url.pathname.startsWith(`/v2/optimization-candidates/${candidate.id}`));
  if (!isAbsence && !isRepair && !isRepairRead) return null;
  if (request.headers.get('X-ShiftPilot-Scenario') === 'denied') return reply('schedule_week.denied');
  if (request.method === 'GET' && url.pathname === `/v2/optimization-runs/${accepted.id}`) return reply('run.repair.widened');
  if (request.method === 'GET' && url.pathname === '/v2/absences') {
    if (url.searchParams.get('outlet_id') !== repair.outlet_id) return unsupported();
    const list = structuredClone(fixtures['absences.list'].response.body) as Schema['AbsenceList'];
    const from = url.searchParams.get('from'); const to = url.searchParams.get('to');
    list.items = list.items.filter(item => (!from || Date.parse(item.end_at) > Date.parse(from)) && (!to || Date.parse(item.start_at) < Date.parse(to)));
    return Response.json(list);
  }
  if (request.method === 'POST' && url.pathname === '/v2/absences' && request.headers.get('Idempotency-Key')) {
    const input = await request.json().catch(() => null) as Record<string, unknown> | null;
    if (!input) return unsupported();
    for (const name of ['absence.report', 'absence.report.requested']) {
      const expected = fixtures[name].request.body as Record<string, unknown>;
      if (Object.keys(input).every(key => key in expected) && Object.entries(expected).every(([key, value]) => key === 'start_at' || key === 'end_at' ? Date.parse(String(input[key])) === Date.parse(String(value)) : input[key] === value)) return reply(name);
    }
  }
  if (isRepair && request.method === 'POST' && request.headers.get('Idempotency-Key')) {
    const expectedPath = `/v2/outlets/${repair.outlet_id}/schedules/${repair.week_start}/repair`;
    const body = await request.json().catch(() => null) as Schema['RepairRequest'] | null;
    if (url.pathname !== expectedPath || !body || body.absence_id !== accepted.absence_id || body.base_version_id !== accepted.base_version_ids[0]) return unsupported();
    if (body.allow_cross_outlet) return request.headers.get('Authorization') === 'Bearer ui-fixture-manager' ? reply('repair.cross_outlet.manager') : unsupported();
    if (body.freeze && ((body.freeze.shift_ids?.length ?? 0) + (body.freeze.employee_ids?.length ?? 0) + (body.freeze.days?.length ?? 0))) {
      const expected = (fixtures['repair.freeze_conflict'].request.body as Schema['RepairRequest']).freeze!;
      const same = (['shift_ids', 'employee_ids', 'days'] as const).every(field => JSON.stringify([...(body.freeze?.[field] ?? [])].sort()) === JSON.stringify([...(expected[field] ?? [])].sort()));
      return same ? reply('repair.freeze_conflict') : unsupported();
    }
    if (body.unlock_logical_shift_ids?.length) return unsupported();
    return reply('repair.accepted');
  }
  // There is no supplied fixture for confirming the listed requested absence,
  // rejecting/cancelling, or materializing a repair candidate. Do not substitute
  // unrelated absence.update.confirm / generation candidate records.
  return unsupported();
}
