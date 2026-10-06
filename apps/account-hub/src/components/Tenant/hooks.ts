import type { TenantOut } from '../../lib/types';

// What a tenant's pieces tell the page around them.
export type TenantHooks = {
  // Something changed that the lists around it may show (a campaign made, a membership left).
  onChanged(): void;
  // The tenant's name or slug was saved.
  onRenamed(updated: TenantOut): void;
};
