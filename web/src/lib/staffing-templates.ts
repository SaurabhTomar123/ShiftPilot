import type { Schema } from '@/api/types';

export function templateProblem(items: Schema['StaffingTemplateBlock'][], skillIds: string[]): string | null {
  if (items.length > 2000) return 'Keep at most 2000 template blocks.';
  for (const [index, item] of items.entries()) {
    if (!Number.isInteger(item.weekday) || item.weekday < 0 || item.weekday > 6 || !skillIds.includes(item.skill_id)) return `Block ${index + 1}: choose a valid weekday and skill.`;
    if (![item.start_minute, item.end_minute].every(value => Number.isInteger(value) && value % 30 === 0) || item.start_minute < 0 || item.start_minute > 1410 || item.end_minute > 1440 || item.end_minute <= item.start_minute) return `Block ${index + 1}: use the half-hour grid and end after the start within the same day. Split overnight staffing across weekdays.`;
    if (![item.minimum_required, item.preferred_required].every(value => Number.isInteger(value) && value >= 0) || item.preferred_required < item.minimum_required) return `Block ${index + 1}: preferred staffing must be at least the nonnegative whole-number minimum.`;
  }
  const sorted = [...items].sort((a, b) => a.weekday - b.weekday || a.skill_id.localeCompare(b.skill_id) || a.start_minute - b.start_minute);
  for (let i = 1; i < sorted.length; i++) { const before = sorted[i - 1], after = sorted[i]; if (before.weekday === after.weekday && before.skill_id === after.skill_id && after.start_minute < before.end_minute) return 'Blocks for the same weekday and skill must not overlap. Adjacent blocks are allowed.'; }
  return null;
}
