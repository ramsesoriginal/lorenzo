// The table is read as text when the consumer is built (Vite's `?raw`).
declare module '*.toml?raw' {
  const text: string;
  export default text;
}
