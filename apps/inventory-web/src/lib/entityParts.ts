// The parts of an entry's page that this app shares with the other apps that draw them
// (packages/entity-parts, ADR 0526), bound to this app's client, so the rest of the app imports them
// from here.
import { createEntityParts } from '@lorenzo/entity-parts';
import { client } from './api';

export const { renderTagEditor } = createEntityParts({ client });
