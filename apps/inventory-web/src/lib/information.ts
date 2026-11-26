// An entity's information, read and written (ADR 0101, 0109): the logic is packages/entity-parts (ADR
// 0526), shared with the other app that writes it; this binds its calls to this app's client and
// languages, so the rest of the app imports as before.
export {
  descriptionDraft,
  type Information,
  type InformationDraft,
  type TextPayload,
  textOf,
} from '@lorenzo/entity-parts';

import { information } from './entityParts';

export const {
  listInformation,
  getDescription,
  createInformation,
  updateInformation,
  deleteInformation,
  addKnower,
  saveDescription,
} = information;
