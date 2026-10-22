import { describe, expect, it } from 'vitest';
import { initialTheme, isCurrentPage, navHref, otherTheme, themeToggleLabel } from '../src/pure';

describe('initialTheme', () => {
  it('prefers a saved choice over the system', () => {
    expect(initialTheme('light', true)).toBe('light');
    expect(initialTheme('dark', false)).toBe('dark');
  });

  it('follows the system without a saved choice, and ignores anything else saved', () => {
    expect(initialTheme(null, true)).toBe('dark');
    expect(initialTheme(null, false)).toBe('light');
    expect(initialTheme('sepia', false)).toBe('light');
  });
});

describe('the theme toggle', () => {
  it('switches to the other theme and names it', () => {
    expect(otherTheme('light')).toBe('dark');
    expect(otherTheme('dark')).toBe('light');
    expect(themeToggleLabel('light')).toBe('Dark theme');
    expect(themeToggleLabel('dark')).toBe('Light theme');
  });
});

describe('navHref', () => {
  it('leaves a page that needs no library as it is', () => {
    expect(navHref({ href: '/' }, null)).toBe('/');
    expect(navHref({ href: '/' }, 'abc')).toBe('/');
  });

  it('puts the library into a library page, and has no address without one', () => {
    expect(navHref({ href: '/events/', needsLibrary: true }, 'my library')).toBe(
      '/events/?tenant=my%20library',
    );
    expect(navHref({ href: '/events/', needsLibrary: true }, null)).toBeNull();
  });
});

describe('isCurrentPage', () => {
  it('compares paths with or without a trailing slash', () => {
    expect(isCurrentPage('/events/', '/events')).toBe(true);
    expect(isCurrentPage('/events/', '/events/')).toBe(true);
    expect(isCurrentPage('/', '/')).toBe(true);
    expect(isCurrentPage('/events/', '/calendar/')).toBe(false);
    expect(isCurrentPage('/', '/events/')).toBe(false);
  });
});
