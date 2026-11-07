// A made-up operator for development and tests. Nothing here is a real person, address or
// contact; a build that uses it says so on every page (ADR 0439).
export const SAMPLE_PROFILE = {
  changedOn: '2026-01-01',
  reviewedOn: null,
  operator: {
    name: 'Sample Operator',
    street: 'Sample Street 1',
    postalCode: '00000',
    city: 'Sample City',
    country: 'Sampleland',
    email: 'operator@example.test',
    secondContact: 'none',
    taxId: { kind: 'none' },
    reportEmail: null,
  },
  supervisoryAuthority: {
    name: 'Sample Data Protection Authority',
    url: 'https://authority.example.test',
  },
  providers: [
    {
      name: 'Sample Identity Provider',
      purpose: { de: 'Anmeldung und Zugangsdaten', en: 'Sign-in and credentials' },
      location: { de: 'Beispielregion', en: 'Sample region' },
      transfer: { de: 'Keine Übermittlung in ein Drittland', en: 'No transfer outside the EU' },
      policyUrl: 'https://provider.example.test/privacy',
    },
  ],
  retention: {
    logs: { de: 'Beispielfrist', en: 'Sample period' },
    backups: { de: 'Beispielfrist', en: 'Sample period' },
    activityLog: { de: 'Beispielfrist', en: 'Sample period' },
  },
  support: { name: 'Sample Support', url: 'https://support.example.test/sample' },
};
