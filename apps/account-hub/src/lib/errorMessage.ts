// What went wrong, as a message to show: an Error's own, else whatever was thrown as text.
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
