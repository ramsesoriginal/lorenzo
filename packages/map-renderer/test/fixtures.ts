import { DEFAULT_GROUPS, type MapModel, type Placement, type System, type View } from '../src';

export const system: System = {
  kind: 'plane',
  extent: [0, 0, 1000, 640],
  scale: { per_unit: 0.5, unit: 'km' },
};

export function place(
  id: string,
  name: string,
  kinds: string[],
  geometry: Placement['geometry']['parts'],
  extra: Partial<Pick<Placement, 'role' | 'style' | 'z'>> = {},
): Placement {
  return {
    entry: { id, name, slug: null, kinds },
    geometry: { format: 'lorenzo.geometry/1', parts: geometry },
    role: null,
    style: null,
    z: 0,
    ...extra,
  };
}

export const river = place(
  'river',
  'The Rushwater',
  ['location'],
  [
    {
      shape: 'polyline',
      pts: [
        [690, -120],
        [730, 60],
        [790, 270],
        [720, 640],
      ],
    },
  ],
  { role: 'water' },
);

export const town = place(
  'town',
  'Hollowmere',
  ['location'],
  [
    {
      shape: 'polygon',
      rings: [
        [
          [300, 200],
          [700, 200],
          [700, 500],
          [300, 500],
        ],
        [
          [450, 300],
          [550, 300],
          [550, 400],
          [450, 400],
        ],
      ],
    },
  ],
  { role: 'built-up' },
);

export const road = place(
  'road',
  'The Mill Road',
  ['connection'],
  [
    {
      shape: 'polyline',
      pts: [
        [100, 100],
        [400, 300],
      ],
    },
  ],
  { role: 'route' },
);

export const stag = place(
  'stag',
  'The Gilded Stag',
  ['location'],
  [{ shape: 'point', at: [400, 300] }],
);
export const shrine = place(
  'shrine',
  'Shrine of the Lantern',
  ['location'],
  [{ shape: 'point', at: [550, 450] }],
);
export const mara = place('mara', 'Mara Quill', ['being'], [{ shape: 'point', at: [410, 330] }], {
  role: 'presence',
});

export const model: MapModel = {
  system,
  placements: [mara, shrine, stag, road, town, river],
};

export function view(over: Partial<View> = {}): View {
  return {
    viewport: { width: 1000, height: 640 },
    zoom: 1,
    centre: [500, 320],
    groups: { ...DEFAULT_GROUPS },
    selection: null,
    ...over,
  };
}
