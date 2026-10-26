import { expect, it } from 'vitest';
import { templateProblem } from './staffing-templates';
import type { Schema } from '../api/types';

const block: Schema['StaffingTemplateBlock'] = { weekday: 0, skill_id: 'prep', start_minute: 600, end_minute: 720, minimum_required: 1, preferred_required: 2 };
it('accepts adjacent blocks, different skills and end-of-day midnight without mutating the set', () => {
  const items = [{ ...block, start_minute: 720, end_minute: 1440 }, block, { ...block, skill_id: 'grill' }]; const before = structuredClone(items);
  expect(templateProblem(items, ['prep', 'grill'])).toBeNull(); expect(items).toEqual(before);
  expect(templateProblem([], ['prep'])).toBeNull();
});
it('rejects overlaps only within the same weekday and skill', () => {
  expect(templateProblem([block, { ...block, start_minute: 690, end_minute: 780 }], ['prep'])).toContain('overlap');
  expect(templateProblem([block, { ...block, weekday: 1 }], ['prep'])).toBeNull();
});
it('rejects off-grid, overnight, unknown-skill and invalid staffing counts', () => {
  for (const patch of [{ start_minute: 615 }, { end_minute: 1470 }, { end_minute: 600 }, { preferred_required: 0 }, { minimum_required: -1 }, { skill_id: 'unknown' }, { weekday: 7 }]) expect(templateProblem([{ ...block, ...patch }], ['prep'])).not.toBeNull();
});
