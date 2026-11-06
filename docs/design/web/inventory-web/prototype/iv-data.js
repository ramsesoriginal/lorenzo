/* Inventory: made-up data for the prototype. */
const MEP = 'imani'; /* the board the player's own character has */
const BOARDS = {
  imani: { n: 'Imani Roe', kind: 'Character', cols: [{ id: 'eq', n: 'Equipped', note: 'Imani holds these', carried: true }, { id: 'nc', n: 'Not carried', note: 'Set down' }, { id: 'bp', n: 'Backpack', note: 'Imani has these', carried: true, cap: 12 }, { id: 'case', n: 'Medical case', note: 'Imani has these', carried: true, cap: 4 }] },
  tobias: { n: 'Tobias Reyes', kind: 'Character', cols: [{ id: 'eq', n: 'Equipped', note: 'Tobias holds these', carried: true }, { id: 'nc', n: 'Not carried', note: 'Set down' }] },
  wen: { n: 'Wen Okafor', kind: 'Character', cols: [{ id: 'eq', n: 'Equipped', note: 'Wen holds these', carried: true }, { id: 'nc', n: 'Not carried', note: 'Set down' }] },
  mara: { n: 'Mara Quill', kind: 'Character', cols: [{ id: 'eq', n: 'Equipped', note: 'Mara holds these', carried: true }, { id: 'nc', n: 'Not carried', note: 'Set down' }, { id: 'chest', n: 'Chest', note: 'Not carried', cap: 40 }] },
  harbour: { n: 'Harbour master', kind: 'NPC', cols: [{ id: 'eq', n: 'Equipped', note: 'Holds these', carried: true }, { id: 'nc', n: 'Not carried', note: 'Set down' }] },
  crew: { n: 'The Thursday crew', kind: 'Group', cols: [{ id: 'nc', n: 'Held by the crew', note: 'The group owns these' }, { id: 'locker', n: 'Locker', note: 'The group owns these', cap: 60 }] },
  stores: { n: 'Station 4 stores', kind: 'Group', cols: [{ id: 'nc', n: 'Held by the group', note: 'The group owns these' }] },
  unowned: { n: 'Unowned things', kind: 'Nobody', cols: [{ id: 'nc', n: 'Not carried', note: 'Nobody owns these' }] },
};
const MINE = ['imani'], GROUPS = ['crew', 'stores'];
const CAT = [
  { id: 'lantern', n: 'Lantern', kind: 'Light source', w: 3, v: 8, public: true, tags: ['Light', 'Fragile'], protos: ['Light source', 'Metalwork'], slug: 'lantern', desc: 'A lantern with a shutter and a brass handle. Burns oil for about six hours.' },
  { id: 'blade', n: 'Short blade', kind: 'Weapon', w: 2, v: 12, public: true, tags: ['Weapon'], protos: ['Weapon'], slug: 'short-blade', desc: 'A short blade with a plain grip, kept sharp.' },
  { id: 'rope', n: 'Rope, hempen', kind: 'Cord', w: 5, v: 2, public: true, tags: ['Cord'], protos: ['Cord'], slug: 'rope-hempen', desc: 'Fifteen metres of hempen rope.' },
  { id: 'rations', n: 'Rations', kind: 'Food', w: 1, v: 1, public: true, tags: ['Food'], protos: ['Food'], slug: 'rations', desc: 'A day of dried food.' },
  { id: 'bandage', n: 'Bandages', kind: 'Medical', w: 0.5, v: 1, public: true, tags: ['Medical'], protos: ['Medical'], slug: 'bandages', desc: 'Clean cloth, rolled.' },
  { id: 'needle', n: 'Needle set', kind: 'Medical', w: 1, v: 6, public: true, tags: ['Medical'], protos: ['Medical'], slug: 'needle-set', desc: 'Curved needles and gut thread.' },
  { id: 'splint', n: 'Splints', kind: 'Medical', w: 1, v: 3, public: false, tags: ['Medical'], protos: ['Medical'], slug: 'splints', desc: 'Two light splints.' },
  { id: 'fieldkit', n: 'Field kit', kind: 'Pack', w: 2, v: 10, public: true, tags: ['Pack'], protos: ['Pack'], slug: 'field-kit', desc: 'A roll of cloth. Holds: Bandages × 2, Needle set × 1.', pack: [['bandage', 2], ['needle', 1]] },
  { id: 'coins', n: 'Loose coins', kind: 'Money', w: 0.1, v: 1, public: false, tags: ['Money'], protos: ['Money'], slug: 'loose-coins', desc: 'A handful of small coins.' },
];
const SPELL = { seil: 'rope', 'rope, hempen': 'rope' };
let ITEMS = [
  { id: 'i1', n: 'Lantern', cat: 'lantern', q: 1, w: 3, owner: 'imani', at: 'imani', col: 'eq', notes: [{ who: 'Imani only', t: 'Left on the shelf, as told. Took it anyway.' }, { who: 'GM only', t: 'It has been lit once by someone else.' }] },
  { id: 'i2', n: 'Short blade', cat: 'blade', q: 1, w: 2, owner: 'imani', at: 'imani', col: 'eq', notes: [] },
  { id: 'i3', n: 'Rope, hempen, 15 m', cat: 'rope', q: 2, w: 5, owner: 'imani', at: 'imani', col: 'nc', notes: [] },
  { id: 'i4', n: 'Brass key', cat: null, unsorted: true, uname: 'Brass key', q: 1, w: 0, owner: 'imani', at: 'imani', col: 'nc', notes: [{ who: 'Imani only', t: 'Found under the stair. Fits nothing yet.' }] },
  { id: 'i5', n: 'Rations', cat: 'rations', q: 6, w: 1, owner: 'imani', at: 'imani', col: 'bp', notes: [] },
  { id: 'i6', n: 'Bandages', cat: 'bandage', q: 4, w: 0.5, owner: 'imani', at: 'imani', col: 'bp', notes: [] },
  { id: 'i7', n: 'Field kit', cat: 'fieldkit', q: 1, w: 2, owner: 'imani', at: 'imani', col: 'bp', notes: [] },
  { id: 'i8', n: 'Needle set', cat: 'needle', q: 1, w: 1, owner: 'imani', at: 'imani', col: 'case', notes: [] },
  { id: 'i9', n: 'Splints', cat: 'splint', q: 2, w: 1, owner: 'imani', at: 'imani', col: 'case', notes: [] },
  { id: 'i10', n: 'Ledger box', cat: null, q: 1, w: 2, owner: 'mara', at: 'imani', col: 'bp', notes: [] },
  { id: 'i11', n: 'Spare lantern', cat: 'lantern', q: 1, w: 3, owner: 'imani', at: 'mara', col: 'chest', notes: [] },
  { id: 'i12', n: 'Ledger', cat: null, q: 1, w: 2, owner: 'mara', at: 'mara', col: 'eq', notes: [] },
  { id: 'i13', n: 'Strongbox', cat: null, q: 1, w: 12, owner: 'mara', at: 'mara', col: 'chest', notes: [] },
  { id: 'i14', n: 'Satchel', cat: null, q: 1, w: 1, owner: 'tobias', at: 'tobias', col: 'eq', notes: [] },
  { id: 'i15', n: 'Seil', cat: null, unsorted: true, uname: 'Seil', q: 2, w: 5, owner: 'tobias', at: 'tobias', col: 'nc', notes: [{ who: 'Tobias only', t: 'From the dock. Strong, good for climbing.' }] },
  { id: 'i16', n: 'Healing herbs', cat: null, unsorted: true, uname: 'Healing herbs', q: 2, w: 0.2, owner: 'tobias', at: 'tobias', col: 'nc', notes: [{ who: 'Tobias only', t: 'Dried, in a twist of paper.' }] },
  { id: 'i17', n: 'Seil', cat: null, unsorted: true, uname: 'Seil', q: 1, w: 5, owner: 'wen', at: 'wen', col: 'nc', notes: [{ who: 'Wen only', t: 'Short piece.' }] },
  { id: 'i18', n: 'Tide table', cat: null, q: 1, w: 0, owner: 'harbour', at: 'harbour', col: 'eq', notes: [] },
  { id: 'i19', n: 'Rope, hempen, 15 m', cat: 'rope', q: 3, w: 5, owner: 'crew', at: 'crew', col: 'locker', notes: [] },
  { id: 'i20', n: 'Loose coins', cat: 'coins', q: 40, w: 0.1, owner: 'unowned', at: 'unowned', col: 'nc', notes: [] },
  { id: 'i21', n: 'Cracked lantern', cat: 'lantern', q: 1, w: 3, owner: 'unowned', at: 'unowned', col: 'nc', notes: [] },
];
