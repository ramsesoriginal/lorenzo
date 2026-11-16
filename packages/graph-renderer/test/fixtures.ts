import { DEFAULT_VIEW, type GraphModel, type GraphView } from '../src';

/** A small family and its allies: every edge status, a one-way tie, two parallel edges and a
 * weighted one. */
export const model: GraphModel = {
  nodes: [
    { id: 'tomas', name: 'Tomas', icon: 'kind-being' },
    { id: 'mara', name: 'Mara' },
    { id: 'wren', name: 'Wren' },
    { id: 'dren', name: 'Dren' },
    { id: 'guild', name: 'The Weavers', icon: 'kind-group' },
    { id: 'loner', name: 'Hollow Anselm' },
  ],
  edges: [
    { id: 'e1', a: 'tomas', b: 'mara', directed: true, label: 'parent of', status: 'direct' },
    { id: 'e2', a: 'mara', b: 'wren', directed: true, label: 'parent of', status: 'direct' },
    { id: 'e3', a: 'tomas', b: 'wren', directed: true, label: 'grandparent of', status: 'derived' },
    { id: 'e4', a: 'wren', b: 'dren', directed: false, label: 'friend of', status: 'uncertain' },
    {
      id: 'e5',
      a: 'wren',
      b: 'dren',
      directed: true,
      label: 'honors',
      status: 'direct',
      value: 8,
      scale: [-10, 10],
    },
    { id: 'e6', a: 'mara', b: 'guild', directed: false, label: 'member of', status: 'direct' },
    { id: 'e7', a: 'dren', b: 'guild', directed: false, status: 'direct' },
  ],
  groups: [{ id: 'family', name: 'Family', members: ['tomas', 'mara', 'wren'] }],
};

export function view(over: Partial<GraphView> = {}): GraphView {
  return { ...DEFAULT_VIEW, width: 640, height: 420, ...over };
}
