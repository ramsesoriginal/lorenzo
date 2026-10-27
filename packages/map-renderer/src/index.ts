export type { Overlay, OverlayShape, Tool, ToolEvent } from './edit';
export { HANDLE_PICK, HANDLE_RADIUS, handleAt, overlayPrims } from './edit';
export { placementCentre } from './geom';
export { hitTest } from './hit';
export { layout } from './layout';
export type { LegendItem } from './legend';
export { legend, SWATCH } from './legend';
export type {
  MapViewController,
  MapViewOptions,
  MapViewState,
} from './mapView';
export { createMapView } from './mapView';
export type { PaintOptions, TreeNode } from './paint';
export { iconHref, paintSvg, sceneToSvg, sceneTree } from './paint';
export { project } from './project';
export type { Arc } from './relief';
export { reliefArcs } from './relief';
export type { CirclePrim, Hit, IconPrim, PathPrim, Prim, RectPrim, Scene, TextPrim } from './scene';
export type {
  DrawableShape,
  DrawMark,
  IconMark,
  Mark,
  MarkInput,
  Shape,
  TextMark,
  Theme,
  ThemeContext,
} from './theme';
export { defaultTheme, iconForKinds, initials, WEIGHT_PX } from './themes/default';
export type { ThemeName } from './themes/index';
export { THEME_NAMES, themeNamed, themes } from './themes/index';
export { plainTheme } from './themes/plain';
export type {
  BBox,
  Geometry,
  GroupName,
  Groups,
  MapModel,
  Part,
  Placement,
  Point,
  Role,
  StrokeStyle,
  Style,
  System,
  View,
  Weight,
} from './types';
export { DEFAULT_GROUPS, groupOf, normaliseRole, ROLE_WORDS, ROLES } from './types';
export type { Viewport, ViewState } from './view';
export {
  centreOn,
  clampCentre,
  clampZoom,
  fitView,
  MAX_ZOOM,
  MIN_ZOOM,
  PAN_STEP,
  panBy,
  sameView,
  screenToDrawing,
  sheetCentre,
  ZOOM_STEP,
  zoomBy,
  zoomLabel,
  zoomTo,
} from './view';
