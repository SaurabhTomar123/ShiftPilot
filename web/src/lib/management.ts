import type { Schema } from '@/api/types';

/** Decimal text is converted through integer arithmetic; never round an hourly rate. */
export function decimalUnits(value: string, scale: number): number | null {
  if (!/^\d+(?:\.\d{1,2})?$/.test(value.trim())) return null;
  const [whole, fraction = ''] = value.trim().split('.');
  const hundredths = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  const result = hundredths * scale / 100;
  return Number.isSafeInteger(hundredths) && Number.isSafeInteger(result) ? result : null;
}

export function employeePatch(before: Schema['Employee'], after: Schema['EmployeeCreate']): Schema['EmployeeUpdate'] {
  const changes = Object.fromEntries(Object.entries(after).filter(([key, value]) => JSON.stringify(before[key as keyof typeof before]) !== JSON.stringify(value)));
  return { base_revision: before.revision, ...changes };
}

export function availabilityProblem(windows: Schema['AvailabilityWindow'][]): string | null {
  if (windows.some(w => !Number.isInteger(w.weekday) || w.weekday < 0 || w.weekday > 6 || !Number.isInteger(w.start_minute) || !Number.isInteger(w.end_minute) || w.start_minute < 0 || w.end_minute > 2880 || w.end_minute <= w.start_minute)) return 'Each window must end after it starts and stay within two days of its weekday.';
  return null;
}

export const minuteTime = (minutes: number) => `${String(Math.floor(minutes % 1440 / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
export const timeMinute = (time: string) => { const [hours, minutes] = time.split(':').map(Number); return hours * 60 + minutes; };

/** Resolve an outlet wall time; reject skipped or repeated clock times rather than guessing. */
export function outletInstant(date: string, time: string, timezone: string): string {
  const target = Date.parse(`${date}T${time}:00Z`);
  if (!Number.isFinite(target)) throw new Error('Choose a valid date and time.');
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
  const wall = (instant: number) => {
    const parts = Object.fromEntries(formatter.formatToParts(instant).map(p => [p.type, p.value]));
    return Date.parse(`${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}Z`);
  };
  const offsets = new Set([-86400000, 0, 86400000].map(delta => wall(target + delta) - target - delta));
  const matches = [...offsets].map(offset => target - offset).filter(instant => wall(instant) === target);
  if (matches.length !== 1) throw new Error('This local time is skipped or repeated by a clock change. Choose another interval.');
  return new Date(matches[0]).toISOString();
}
