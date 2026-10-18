import { DemoState, Employee, OutletId, Shift, roles, outlets } from './types';

const names = [
  'Ravi Kumar', 'Neha Sharma', 'Arjun Rao', 'Priya Nair', 'Aman Singh',
  'Meera Iyer', 'Karan Patel', 'Ananya Das', 'Dev Mehta', 'Isha Reddy',
  'Vikram Joshi', 'Tara Shah', 'Rohan Gupta', 'Diya Menon', 'Aditya Sen',
  'Sana Khan', 'Nikhil Jain', 'Pooja Bhat', 'Rahul Verma', 'Kavya Rao',
  'Akash Pai', 'Naina Kapoor', 'Varun Sethi', 'Simran Gill', 'Harsh Vyas',
  'Aditi Roy', 'Pranav Shetty', 'Sneha Bose', 'Yash Kulkarni', 'Riya Saha',
  'Abhay Rao', 'Maya Thomas', 'Kabir Ali', 'Leela Nair', 'Om Prakash',
  'Zoya Mir', 'Manav Suri', 'Nidhi Desai', 'Sahil Arora', 'Avni Shah',
  'Dhruv Bansal', 'Anika Pillai', 'Ishaan Sood', 'Reva Patil', 'Arnav Das',
  'Siya Anand', 'Ved Narayan', 'Myra Dutta', 'Krish Malik', 'Asha Paul',
  'Aryan Bajaj', 'Jiya Nath', 'Rehan Ahmed', 'Esha Chopra', 'Neil Dsouza',
  'Alia George', 'Vivaan Rao', 'Ritu Mishra', 'Parth Shah', 'Uma Hegde',
];
const colors = ['sage', 'rose', 'sand', 'lilac', 'blue'];

export function createDemo(): DemoState {
  const employees: Employee[] = names.map((name, i) => ({
    id: `emp-${i + 1}`, name, role: roles[i % 4], outletId: outlets[Math.floor(i / 20)].id,
    rate: [210, 180, 170, 190][i % 4], maxHours: 48,
    initials: name.split(' ').map(n => n[0]).slice(0, 2).join(''), color: colors[i % colors.length],
  }));
  return {
    schemaVersion: 1, employees, rosters: {}, versions: [], demand: {},
    rules: [
      { id: 'rest', name: 'Time to recharge', description: 'At least 10 hours between working days.', active: true, kind: 'Hard rule' },
      { id: 'hours', name: 'Weekly hours limit', description: 'Keep each employee within their configured weekly maximum.', active: true, kind: 'Hard rule' },
      { id: 'locks', name: 'Keep locked shifts', description: 'Preserve assignments a manager has locked.', active: true, kind: 'Hard rule' },
      { id: 'home', name: 'Home outlet first', description: 'Prefer an employee’s home outlet when possible.', active: true, kind: 'Preference' },
    ],
    requests: [
      { id: 'req-1', outletId: 'indiranagar', employee: 'Neha Sharma', type: 'Time off', detail: 'Saturday, 24 October · Personal appointment', status: 'Pending' },
      { id: 'req-2', outletId: 'indiranagar', employee: 'Aman Singh', type: 'Availability', detail: 'From next week · Available after 12:00 on Tuesdays', status: 'Pending' },
      { id: 'req-3', outletId: 'indiranagar', employee: 'Isha Reddy', type: 'Shift swap', detail: 'Friday closing shift · Swap with Meera Iyer', status: 'Pending' },
    ],
  };
}

/** Synthetic roster fixture. This is not optimization or backend validation. */
export function makeRoster(employees: Employee[], outletId: OutletId): Shift[] {
  return employees.filter(e => e.outletId === outletId).flatMap((employee, index) =>
    Array.from({ length: 7 }, (_, day) => {
      if ((day + index) % 7 === 2 || (day + index) % 7 === 5) return null;
      const late = (index + day) % 3 === 0;
      return {
        id: `${outletId}-${employee.id}-${day}`, employeeId: employee.id, day,
        start: late ? '14:00' : '10:00', end: late ? '22:00' : '18:00', role: employee.role,
        locked: index === 0 && day === 3,
      };
    }).filter((shift): shift is Shift => shift !== null),
  );
}

export function readDemo(value: string | null): DemoState {
  if (!value) return createDemo();
  try {
    const parsed = JSON.parse(value) as DemoState;
    if (parsed.schemaVersion !== 1 || !Array.isArray(parsed.employees) || !parsed.rosters || !Array.isArray(parsed.versions) || !Array.isArray(parsed.rules) || !Array.isArray(parsed.requests) || !parsed.demand) return createDemo();
    return parsed;
  } catch { return createDemo(); }
}
