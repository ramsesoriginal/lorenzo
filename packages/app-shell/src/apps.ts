// The apps by job, for the apps drawer and the More sheet (ADR 0410, D17). The registry
// (`GET /app-links`, ADR 0273) says which apps are deployed and where; this says what each is
// called and where it sits. An app the registry has no address for is not listed, and neither is
// an empty group.

export type AppId =
  | 'sessions'
  | 'beings'
  | 'inventory_web'
  | 'calendars'
  | 'maps'
  | 'social'
  | 'writing'
  | 'bench'
  | 'account_hub';

type AppInfo = { name: string; icon: string; description: string };

export const APP_INFO: Record<AppId, AppInfo> = {
  sessions: { name: 'Sessions', icon: 'kind-session', description: 'Plan and run your games' },
  beings: {
    name: 'Beings',
    icon: 'kind-being',
    description: 'Characters and non-player characters',
  },
  inventory_web: { name: 'Inventory', icon: 'inventory', description: 'What people carry' },
  calendars: { name: 'Calendars', icon: 'kind-calendar', description: 'Time in your world' },
  maps: { name: 'Maps', icon: 'map', description: 'Places and maps' },
  social: { name: 'Social', icon: 'social', description: 'Who is tied to whom' },
  writing: { name: 'Writing', icon: 'manuscript', description: 'Manuscripts and books' },
  bench: { name: 'Bench', icon: 'layout-write', description: 'Build and edit a repository' },
  account_hub: {
    name: 'Account',
    icon: 'account',
    description: 'People, libraries, repositories and tokens',
  },
};

/** The groups, in the order of the design (D17, D30, D31). */
export const JOBS: { label: string; apps: AppId[] }[] = [
  { label: 'Play', apps: ['sessions', 'beings', 'inventory_web'] },
  { label: 'World', apps: ['calendars', 'maps', 'social'] },
  { label: 'Build', apps: ['writing', 'bench'] },
  { label: 'You', apps: ['account_hub'] },
];

/** What `GET /app-links` answers that the shell reads: the apps and their addresses. */
export type AppRegistry = {
  // An app may be null in the registry (an app the deployment does not run).
  apps: Record<string, { url?: string } | null | undefined>;
  // The legal links and the support address, when the deployment has them (ADR 0439).
  links?: Record<string, string | undefined>;
  support_url?: string | null;
};

export type JobApp = AppInfo & { id: AppId; url: string };
export type Job = { label: string; apps: JobApp[] };

/** The deployed apps by job. The app the person is in is listed too: the list is the same on every page. */
export function appsByJob(registry: AppRegistry): Job[] {
  return JOBS.map((job) => ({
    label: job.label,
    apps: job.apps.flatMap((id) => {
      const url = registry.apps[id]?.url?.trim();

      return url ? [{ id, url, ...APP_INFO[id] }] : [];
    }),
  })).filter((job) => job.apps.length > 0);
}
