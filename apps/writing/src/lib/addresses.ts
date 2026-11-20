/** The old one-page addresses open the new ones (ADR 0494, Q5); `?review=` is never changed. */
export function modernAddress(location: Pick<Location, 'pathname' | 'search' | 'hash'>) {
  if (location.pathname !== '/') return null;
  const params = new URLSearchParams(location.search);
  if (params.get('review') || !params.get('entry')) return null;
  const view = params.get('view');
  params.delete('view');
  if (view === 'read') return `/read/?${params}${location.hash}`;
  if (view) params.set('view', view);
  return `/write/?${params}${location.hash}`;
}
