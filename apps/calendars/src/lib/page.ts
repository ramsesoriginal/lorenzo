import { calendarReads } from './read-cache';
// Astro keeps these modules alive between static pages; every protected view starts afresh.
export function onPage(id: string, mount: () => Promise<void>) {
  const show = () => {
    if (document.getElementById(id)) void mount();
  };
  document.addEventListener('astro:page-load', show);
  show();
}
document.addEventListener('astro:before-swap', () => calendarReads.suspend());
