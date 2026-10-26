'use client';

import { ApiError } from '@/api/client';
import { Button } from './primitives/button';

export function FormProblem({ error, reload }: { error: Error; reload?: () => void }) {
  const detail = error instanceof ApiError ? error.detail : null;
  const fields: unknown = detail?.details?.fields;
  return <div className="form-problem" role="alert"><strong>{detail?.code === 'stale_version' ? 'Someone changed these values.' : 'Changes were not confirmed.'}</strong><p>{error.message}</p>{Array.isArray(fields) && <ul>{fields.map((field: unknown, i) => { const value = (field && typeof field === 'object' ? field : {}) as { path?: unknown; message?: unknown }; return typeof value.message === 'string' ? <li key={i}>{Array.isArray(value.path) ? `${value.path.join(' / ')}: ` : ''}{value.message}</li> : null; })}</ul>}{detail?.trace_id && <small>Support trace: {detail.trace_id}</small>}{detail?.code === 'stale_version' && reload && <><p>Your inputs are still here. Reloading replaces them with the latest saved values.</p><Button type="button" onClick={reload}>Reload latest values</Button></>}</div>;
}
