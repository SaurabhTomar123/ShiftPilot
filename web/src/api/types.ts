import type { components } from './generated/schema';

export type Schema = components['schemas'];
export type Persona = Schema['DemoSessionRequest']['persona'];
export type Capability = Schema['Me']['capabilities'][number];
export type Scenario = 'optimal' | 'feasible' | 'infeasible' | 'timeout' | 'failed' | 'stale' | 'denied';
export type ApiErrorBody = Schema['ErrorBody'];
export type Fixture = {
  name: string; operation_id: string; method: string; path: string; persona: string;
  request: { path_params?: Record<string, string>; query?: Record<string, unknown>; body?: unknown };
  response: { status: number; schema: string; body: unknown };
};
