// An .astro file is a component for Astro's container; the tests hand it over as it is.
declare module '*.astro' {
  const component: never;
  export default component;
}
