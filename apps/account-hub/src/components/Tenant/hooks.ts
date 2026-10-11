import type { TenantOut, TenantSummaryOut } from '../../lib/types';

// What a tenant's pieces tell the page around them.
export type TenantHooks = {
  // Something changed that the lists around it may show (a campaign made, a membership left).
  onChanged(): void;
  // The tenant's name or slug was saved.
  onRenamed(updated: TenantOut): void;
  // The tenant was deleted (ADR 0267): the message to show where the page goes next.
  onDeleted(message: string, tenant: TenantSummaryOut): void;
};
