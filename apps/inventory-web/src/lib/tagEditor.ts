// Three-state tag editing (ADR 0103, 0112): the logic is packages/entity-parts (ADR 0526), shared
// with the other app that draws tags; this binds its calls to this app's client, so the rest of the
// app imports as before. The editor itself is in the package.
import * as parts from '@lorenzo/entity-parts';
import { client } from './api';

export { type Definition, STATES, type State, tagState } from '@lorenzo/entity-parts';

export const tagDefinitions = (tenantId: string) => parts.tagDefinitions(client, tenantId);

export const setTag = (
  tenantId: string,
  entityId: string,
  definitionId: string,
  state: parts.State,
) => parts.setTag(client, tenantId, entityId, definitionId, state);
