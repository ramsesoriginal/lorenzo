import { type Block, bi, type Doc, same } from '../doc';
import type { LegalProfile } from '../profile';

// The legal notice (Impressum). Built only from the operator profile and facts that are true of
// every deployment. It adds no legal boilerplate beyond what § 5 DDG lists (ADR 0439); whether
// more is needed is a question for the lawyer.
export function noticeDoc(profile: LegalProfile): Doc {
  const { operator } = profile;
  const reports = operator.reportEmail ?? operator.email;
  const contact: Block[] = [{ p: bi(`E-Mail: ${operator.email}`, `Email: ${operator.email}`) }];
  if (operator.secondContact !== 'none') {
    contact.push({
      p: bi(
        `Weiterer Kontakt: ${operator.secondContact}`,
        `Other contact: ${operator.secondContact}`,
      ),
    });
  }

  const sections: Doc['sections'] = [
    {
      id: 'provider',
      heading: bi('Anbieter', 'Provider'),
      blocks: [
        { p: same(operator.name) },
        { p: same(operator.street) },
        { p: same(`${operator.postalCode} ${operator.city}`) },
        { p: same(operator.country) },
      ],
    },
    { id: 'contact', heading: bi('Kontakt', 'Contact'), blocks: contact },
  ];

  if (operator.taxId.kind !== 'none') {
    const { kind, value } = operator.taxId;
    sections.push({
      id: 'tax',
      heading: bi('Steuerliche Angaben', 'Tax details'),
      blocks: [
        {
          p:
            kind === 'vat'
              ? bi(
                  `Umsatzsteuer-Identifikationsnummer nach § 27a UStG: ${value}`,
                  `VAT identification number under § 27a UStG: ${value}`,
                )
              : bi(
                  `Wirtschafts-Identifikationsnummer nach § 139c AO: ${value}`,
                  `Business identification number under § 139c AO: ${value}`,
                ),
        },
      ],
    });
  }

  sections.push(
    {
      id: 'reports',
      heading: bi('Inhalte melden', 'Reporting content'),
      blocks: [
        {
          p: bi(
            `Wer Inhalte in Lorenzo für rechtswidrig hält, kann das an ${reports} melden. Ein öffentliches Repository kann zusätzlich einen Link „Dieses Repository melden“ haben.`,
            `Anyone who considers content in Lorenzo unlawful can report it to ${reports}. A public repository can also have a "Report this repository" link.`,
          ),
        },
      ],
    },
    {
      id: 'source',
      heading: bi('Quellcode und Lizenz', 'Source code and licence'),
      blocks: [
        {
          p: bi(
            'Lorenzo ist freie Software unter der GNU Affero General Public License, Version 3. Der Quellcode ist unter https://github.com/ramsesoriginal/lorenzo verfügbar.',
            'Lorenzo is free software under the GNU Affero General Public License, version 3. The source code is available at https://github.com/ramsesoriginal/lorenzo.',
          ),
        },
      ],
    },
  );

  if (profile.support) {
    sections.push({
      id: 'support',
      heading: bi('Unterstützung', 'Support'),
      blocks: [
        {
          p: bi(
            `Lorenzo kann über ${profile.support.name} unterstützt werden: ${profile.support.url}. Das ist ein Link auf eine fremde Seite; Lorenzo bindet davon nichts ein.`,
            `Lorenzo can be supported through ${profile.support.name}: ${profile.support.url}. This is a link to another site; Lorenzo embeds nothing from it.`,
          ),
        },
      ],
    });
  }

  return { title: bi('Impressum', 'Legal notice'), sections };
}
