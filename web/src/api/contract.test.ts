import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';
import records from './generated/fixtures.json';
import manifest from './generated/manifest.json';
import type { Fixture } from './types';

const openapi = JSON.parse(readFileSync(fileURLToPath(new URL('../../../contracts/v2/openapi.json', import.meta.url)), 'utf8'));
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);

describe(`consumer fixtures ${manifest.version}`, () => {
  it('has the complete provider fixture index', () => { expect(Object.keys(records)).toHaveLength(manifest.fixtureCount); });
  for (const [name, value] of Object.entries(records as unknown as Record<string, Fixture>)) {
    it(`parses ${name} against its provider response schema`, () => {
      const operation = openapi.paths[value.path]?.[value.method.toLowerCase()];
      expect(operation?.operationId).toBe(value.operation_id);
      if (value.response.status === 304) {
        expect(operation?.responses['304']).toBeDefined();
        expect(value.response.schema).toBeNull();
        expect(value.response.body).toBeNull();
        expect(value.response.headers?.ETag).toBeTruthy();
        return;
      }
      for (const header of Object.keys(value.response.headers ?? {})) expect(operation?.responses[String(value.response.status)]?.headers?.[header]).toBeDefined();
      expect(operation?.responses[String(value.response.status)]?.content?.['application/json']?.schema?.$ref).toBe(`#/components/schemas/${value.response.schema}`);
      const validate = ajv.compile({ $ref: `#/components/schemas/${value.response.schema}`, components: openapi.components });
      expect(validate(value.response.body), JSON.stringify(validate.errors)).toBe(true);
    });
  }
});
