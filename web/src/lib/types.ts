export type Role = 'Kitchen' | 'Service' | 'Cashier' | 'Barista';
export type View = 'Schedule' | 'Team' | 'Demand' | 'Requests' | 'Rules' | 'History';
export type OutletId = 'indiranagar' | 'koramangala' | 'whitefield';

export interface Employee {
  id: string;
  name: string;
  role: Role;
  outletId: OutletId;
  rate: number;
  maxHours: number;
  initials: string;
  color: string;
}

export interface Shift {
  id: string;
  employeeId: string;
  day: number;
  start: string;
  end: string;
  role: Role;
  locked: boolean;
  absent?: boolean;
}

export interface Version {
  id: string;
  label: string;
  at: string;
  outletId: OutletId;
  week: string;
  shifts: Shift[];
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  active: boolean;
  kind: 'Hard rule' | 'Preference';
}

export interface StaffRequest {
  id: string;
  outletId: OutletId;
  employee: string;
  type: string;
  detail: string;
  status: 'Pending' | 'Approved' | 'Declined';
}

export interface DemoState {
  schemaVersion: 1;
  employees: Employee[];
  rosters: Record<string, Shift[]>;
  versions: Version[];
  rules: Rule[];
  requests: StaffRequest[];
  demand: Record<string, number[]>;
}

export const outlets: { id: OutletId; name: string; address: string }[] = [
  { id: 'indiranagar', name: 'Indiranagar', address: '100 Feet Road, Bengaluru' },
  { id: 'koramangala', name: 'Koramangala', address: '5th Block, Bengaluru' },
  { id: 'whitefield', name: 'Whitefield', address: 'ITPL Main Road, Bengaluru' },
];

export const roles: Role[] = ['Kitchen', 'Service', 'Cashier', 'Barista'];
export const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const DEMO_WEEK = '2026-10-19';
export const STORAGE_KEY = 'shiftpilot-ui-demo-v1';
export const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
export const roleClass = (role: Role) => role.toLowerCase();
export const rosterKey = (outlet: OutletId, week: string) => `${outlet}:${week}`;

export function addDays(iso: string, count: number) {
  const date = new Date(`${iso}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + count);
  return date.toISOString().slice(0, 10);
}

export function formatDate(iso: string, options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' }) {
  return new Intl.DateTimeFormat('en-GB', { ...options, timeZone: 'UTC' }).format(new Date(`${iso}T12:00:00Z`));
}

export function duration(start: string, end: string) {
  const minutes = (time: string) => Number(time.slice(0, 2)) * 60 + Number(time.slice(3));
  return ((minutes(end) - minutes(start) + 1440) % 1440) / 60;
}

export function shiftHours(shifts: Shift[], employeeId: string) {
  return shifts.filter(s => s.employeeId === employeeId && !s.absent).reduce((sum, s) => sum + duration(s.start, s.end), 0);
}
