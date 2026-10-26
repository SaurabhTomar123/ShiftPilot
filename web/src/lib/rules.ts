import type { Schema } from '@/api/types';

/** Identity only: never calculate scope membership, precedence, conflicts or impact here. */
export function ruleIdentity(value: unknown): string { return JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item); }

export function checkedRule(value: Schema['RuleDefinition'], owner: boolean, outletId: string, employeeIds: string[]): Schema['RuleDefinition'] {
  if (value.hard === false) throw new Error('Only required scheduling rules are supported.');
  if (!owner && ['organization', 'tag'].includes(value.scope_level)) throw new Error('Organization and tag rules require an owner.');
  if (value.scope_level === 'outlet' && value.scope.outlet_id !== outletId) throw new Error('Choose the current outlet for an outlet rule.');
  if (value.scope_level === 'employee' && !employeeIds.includes(value.scope.employee_id)) throw new Error('Choose a person from the selected outlet.');
  if (value.scope_level === 'tag' && !value.scope.tag?.trim()) throw new Error('Enter the employee tag.');
  if (value.rule_type === 'max_days_per_week') {
    const days = value.parameters.days;
    if (typeof days !== 'number' || !Number.isInteger(days) || days < 1 || days > 7) throw new Error('Maximum working days must be a whole number from 1 to 7.');
  } else {
    const minute = value.parameters.latest_end_minute, days = value.parameters.weekdays;
    if (typeof minute !== 'number' || !Number.isInteger(minute) || minute < 0 || minute > 1440 || minute % 30) throw new Error('Choose a latest finish on the half-hour grid.');
    if (!Array.isArray(days) || !days.length || days.some(day => !Number.isInteger(day) || day < 0 || day > 6) || new Set(days).size !== days.length) throw new Error('Choose valid weekdays for the latest-finish rule.');
  }
  if ((value.source_text?.length ?? 0) > 500) throw new Error('Keep rule notes within 500 characters.');
  return { rule_type: value.rule_type, scope_level: value.scope_level, scope: value.scope_level === 'organization' ? {} : value.scope_level === 'outlet' ? { outlet_id: outletId } : value.scope_level === 'employee' ? { employee_id: value.scope.employee_id } : { tag: value.scope.tag.trim() }, parameters: value.parameters, hard: true, overrides_rule_id: value.overrides_rule_id ?? null, source_text: value.source_text?.trim() || null };
}

/** Keep each returned time's own offset, including impacts in other outlets. */
export function ruleImpactTime(value: string) { return `${value.slice(0, 16).replace('T', ' ')} ${value.endsWith('Z') ? 'UTC' : `UTC${value.slice(-6)}`}`; }
