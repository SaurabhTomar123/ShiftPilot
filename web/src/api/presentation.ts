import type { Schema } from './types';

export function formatMoney(value: Schema['Money']) {
  if (!Number.isSafeInteger(value.amount_paise)) throw new Error('Money must be integer paise.');
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: value.currency ?? 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value.amount_paise / 100);
}

export const percent = (value: number | null) => value === null ? 'Not applicable' : new Intl.NumberFormat('en-IN', { style: 'percent', maximumFractionDigits: 1 }).format(value);
export const localDate = (instant: string, timezone: string) => new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(instant));
export const localTime = (instant: string, timezone: string) => new Intl.DateTimeFormat('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(instant));

export function runMessage(run: Schema['OptimizationRun']) {
  if (run.job_state === 'queued') return { title: 'Your week is in the queue.', body: 'Waiting for the scheduling worker.', tone: 'neutral' };
  if (run.job_state === 'running') return { title: 'Working through the possibilities.', body: 'Your published schedule stays in place.', tone: 'neutral' };
  if (run.job_state === 'cancelled') return { title: 'This run was cancelled.', body: 'Your published schedule has not been replaced by this run.', tone: 'neutral' };
  if (run.job_state === 'failed') return { title: 'The optimizer could not finish.', body: run.error?.message ?? 'Check the run details before starting another request.', tone: 'warning' };
  if (run.solver_status === 'INFEASIBLE') return { title: 'These requirements cannot all be met.', body: run.infeasibility?.summary ?? 'Review staffing requirements and the constraints below.', tone: 'warning' };
  if (run.solver_status === 'UNKNOWN') return { title: 'No solution found within the time limit.', body: 'This does not mean the schedule is impossible. You can try a longer solve after reviewing this run.', tone: 'warning' };
  if (run.solver_status === 'FEASIBLE') return { title: 'A valid draft, with room to improve.', body: 'The search reached its time limit before optimality was proven.', tone: 'neutral' };
  if (run.solver_status === 'OPTIMAL') return { title: 'Drafts ready for a closer look.', body: 'Optimality is reported by this fixture for its configured objective. Nothing has been published.', tone: 'neutral' };
  return { title: 'No usable result is available.', body: 'Review the run status before trying again.', tone: 'warning' };
}
