import { type Block, bi, type Doc, same } from '../doc';
import type { LegalProfile } from '../profile';
import { STORAGE_KEYS } from '../storage-keys';

// The privacy policy. The fixed text says what Lorenzo does, taken from the code and the ADRs on
// 2026-11-07; the operator profile supplies who the operator is, the providers and the periods.
// Statements about legal bases are drafts for the lawyer (ADR 0439, "Open questions").
export function policyDoc(profile: LegalProfile): Doc {
  const { operator } = profile;
  const sections: Doc['sections'] = [];
  const add = (id: string, heading: ReturnType<typeof bi>, ...blocks: Block[]) =>
    sections.push({ id, heading, blocks });

  add(
    'controller',
    bi('Verantwortlicher', 'Controller'),
    {
      p: bi(
        `${operator.name}, ${operator.street}, ${operator.postalCode} ${operator.city}, ${operator.country}. E-Mail: ${operator.email}.`,
        `${operator.name}, ${operator.street}, ${operator.postalCode} ${operator.city}, ${operator.country}. Email: ${operator.email}.`,
      ),
    },
    {
      p: bi(
        'Diese Erklärung gilt für die Lorenzo-Web-Apps und deren Schnittstelle (API) sowie für den Discord-Bot, die Kommandozeile und die Android- und iOS-App, soweit sie diesen Betreiber nutzen. Wer Lorenzo selbst betreibt, ist für seinen Betrieb selbst verantwortlich.',
        'This policy covers the Lorenzo web apps and their API, and the Discord bot, the command line and the Android and iOS apps where they use this operator. Whoever runs Lorenzo themselves is responsible for their own deployment.',
      ),
    },
  );

  add(
    'account',
    bi('Konto und Anmeldung', 'Account and sign-in'),
    {
      p: bi(
        'Die Anmeldung läuft über Authgear (siehe „Empfänger“). Dort liegen Ihre Zugangsdaten, zum Beispiel Passwort und Anmeldemethoden. Lorenzo speichert die Kennung, die Authgear Ihnen gibt, eine Kopie Ihrer bestätigten E-Mail-Adresse (sie wird nur von Authgear übernommen, nie in Lorenzo geändert) und, wenn Sie sie angeben, Spitzname, Anzeigename, Pronomen, Kurzbeschreibung, Sprachen, eine Farbe und ein Profilbild.',
        'Sign-in runs through Authgear (see "Recipients"). Your credentials, such as password and sign-in methods, are kept there. Lorenzo stores the identifier Authgear gives you, a copy of your verified email address (taken from Authgear only, never changed in Lorenzo) and, if you give them, a nickname, display name, pronouns, short bio, languages, a colour and a profile picture.',
      ),
    },
    {
      p: bi(
        'Zweck: Ihr Konto bereitstellen und Sie in Ihren Bibliotheken erkennen. Grundlage: Vertrag, Art. 6 Abs. 1 lit. b DSGVO.',
        'Purpose: to provide your account and to recognise you in your libraries. Basis: contract, Art. 6(1)(b) GDPR.',
      ),
    },
  );

  add(
    'content',
    bi('Inhalte in Bibliotheken', 'Content in libraries'),
    {
      p: bi(
        'Eine Bibliothek gehört einer Spielrunde oder einem Autor. Ihre Mitglieder schreiben dort Einträge, Notizen und Geheimnisse und legen fest, wer sie sehen darf. Dazu gehören Angaben über Mitspielende und ihre Figuren: die Zuordnung eines Kontos zu einer Kampagne, Figuren und Texte, die ein Spielleiter über sie schreibt. Welche Rolle Sie haben, bestimmt, was Sie lesen können.',
        'A library belongs to a game group or an author. Its members write entries, notes and secrets there and decide who may see them. This includes information about the people who play and their characters: which account belongs to which campaign, characters, and text a game master writes about them. Your role decides what you can read.',
      ),
    },
    {
      p: bi(
        'Zu einem Eintrag wird gespeichert, welches Konto ihn angelegt und zuletzt geändert hat. Wer in einer Bibliothek schreibt, entscheidet über diesen Inhalt. Grundlage: Vertrag, Art. 6 Abs. 1 lit. b DSGVO, und berechtigtes Interesse an einer nachvollziehbaren gemeinsamen Arbeit, lit. f.',
        'For each entry, Lorenzo stores which account created it and which changed it last. Whoever writes in a library decides that content. Basis: contract, Art. 6(1)(b) GDPR, and a legitimate interest in shared work that can be followed, (f).',
      ),
    },
  );

  add(
    'activity',
    bi('Aktivitätsprotokoll und Benachrichtigungen', 'Activity log and notifications'),
    {
      p: bi(
        'Für die Verwalter einer Bibliothek führt Lorenzo ein Protokoll darüber, wer was verändert hat: wer Mitglied wurde oder ging, wer eine Kampagne anlegte oder löschte, wer Zugriffe oder Besitz änderte. Es enthält Kennungen, Zahlen und Stichworte, keine Texte der Einträge. Benachrichtigungen informieren Sie über Ereignisse in Ihren Bibliotheken, zum Beispiel wenn eine Mitgliedschaft endet.',
        'For the administrators of a library, Lorenzo keeps a log of who changed what: who became a member or left, who created or deleted a campaign, who changed access or ownership. It holds identifiers, counts and keywords, not the text of entries. Notifications tell you about events in your libraries, for example when a membership ends.',
      ),
    },
    {
      p: bi(
        'Zweck: Nachvollziehbarkeit und Schutz der Bibliotheken. Grundlage: berechtigtes Interesse, Art. 6 Abs. 1 lit. f DSGVO.',
        'Purpose: accountability and protection of libraries. Basis: legitimate interest, Art. 6(1)(f) GDPR.',
      ),
    },
  );

  add('tokens', bi('Zugriffstoken', 'Access tokens'), {
    p: bi(
      'Wenn Sie ein Gerät, die Kommandozeile oder eine App verbinden, können Sie ein persönliches Zugriffstoken erzeugen. Lorenzo speichert nur einen Hashwert, den Namen, den Sie vergeben, den Zeitpunkt der Erstellung und der letzten Nutzung sowie ein Ablaufdatum, falls Sie eines setzen. Sie sehen und widerrufen Ihre Token im Profil.',
      'When you connect a device, the command line or an app, you can create a personal access token. Lorenzo stores only a hash, the name you give, when it was created and last used, and an expiry date if you set one. You see and revoke your tokens in your profile.',
    ),
  });

  add(
    'pictures',
    bi('Profilbilder und das Gravatar-Bild', 'Profile pictures and the Gravatar picture'),
    {
      p: bi(
        'Ein hochgeladenes Profilbild liegt in der Datenbank. Es wird ohne Anmeldung ausgeliefert: wer die zufällige Kennung Ihres Kontos kennt, kann es abrufen.',
        'An uploaded profile picture is stored in the database. It is served without sign-in: whoever knows the random identifier of your account can fetch it.',
      ),
    },
    {
      p: bi(
        'Wenn Lorenzo Ihre E-Mail-Adresse zum ersten Mal von Authgear übernimmt und Sie noch kein Bild haben, fragt Lorenzo einmal bei Gravatar (Automattic, USA) nach einem Bild zu einem Hashwert (SHA-256) Ihrer E-Mail-Adresse. Gibt es eines, wird es als Ihr Profilbild in Lorenzo gespeichert. Danach fragt Lorenzo nie wieder bei Gravatar nach, und Ihr Browser spricht nie mit Gravatar. Bei bereits bestehenden Konten fragt Lorenzo nicht nach. Sie können das Bild jederzeit ersetzen oder löschen; es wird nicht erneut geholt.',
        'When Lorenzo first takes your email address from Authgear and you have no picture yet, Lorenzo asks Gravatar (Automattic, USA) once for a picture for a hash (SHA-256) of your email address. If there is one, it is stored as your profile picture in Lorenzo. After that Lorenzo never asks Gravatar again, and your browser never talks to Gravatar. For accounts that already existed, Lorenzo does not ask. You can replace or delete the picture at any time; it is not fetched again.',
      ),
    },
    {
      p: bi(
        'Grundlage für die einmalige Anfrage: berechtigtes Interesse, Art. 6 Abs. 1 lit. f DSGVO. Dem können Sie widersprechen, indem Sie das Bild löschen oder uns schreiben.',
        'Basis for the single request: legitimate interest, Art. 6(1)(f) GDPR. You can object by deleting the picture or by writing to us.',
      ),
    },
  );

  add('public', bi('Öffentliche Repositories', 'Public repositories'), {
    p: bi(
      'Wer ein Repository veröffentlicht, wird als Herausgeber mit dem Anzeigenamen seines Kontos genannt (sonst mit dem Spitznamen, sonst als „A Lorenzo account“). Das sehen alle, auch ohne Konto. Bibliotheken, die ein öffentliches Repository selbst kopiert haben, werden dem Herausgeber nur gezählt, nicht genannt.',
      'Whoever publishes a repository is named as its publisher by the display name of their account (otherwise the nickname, otherwise "A Lorenzo account"). Everyone sees this, signed in or not. Libraries that copied a public repository by themselves are only counted for the publisher, never named.',
    ),
  });

  add('invites', bi('Einladungslinks', 'Invite links'), {
    p: bi(
      'Ein Einladungslink enthält ein Geheimnis in der Adresse. Lorenzo speichert davon nur einen Hashwert, entfernt es aus seinen Protokollen und sendet es nicht an andere Seiten weiter. Wer einen Link einlöst, erhält einen Platz in der Kampagne; das steht im Aktivitätsprotokoll.',
      'An invite link carries a secret in its address. Lorenzo stores only a hash of it, removes it from its logs and does not pass it on to other sites. Whoever redeems a link gets a seat in the campaign; the activity log records this.',
    ),
  });

  add(
    'clients',
    bi('Discord-Bot, Kommandozeile und mobile Apps', 'Discord bot, command line and mobile apps'),
    {
      ul: [
        bi(
          'Discord-Bot: Wenn Sie Ihr Discord-Konto verknüpfen, speichert er Ihre Discord-Nutzerkennung und Ihre Anmelde-Token verschlüsselt (AES-GCM). Er liest Ihre eigenen Daten mit Ihrer Berechtigung und kann Benachrichtigungen als Direktnachricht senden. Was Discord selbst verarbeitet, regelt Discord.',
          'Discord bot: when you link your Discord account, it stores your Discord user identifier and your sign-in tokens, encrypted (AES-GCM). It reads your own data with your permission and can send notifications as a direct message. What Discord itself processes is governed by Discord.',
        ),
        bi(
          'Kommandozeile: Sie speichert Ihre Zugangsdaten in einer Datei auf Ihrem Rechner (nur für Ihr Benutzerkonto lesbar). Nichts davon geht an Dritte.',
          'Command line: it stores your credentials in a file on your computer (readable by your user only). Nothing goes to third parties.',
        ),
        bi(
          'Android- und iOS-App: Sie halten verschlüsselte lokale Kopien Ihrer Inventare, Notizen und Entwürfe, bis Sie sich abmelden oder die Anmeldung abläuft.',
          'Android and iOS apps: they keep encrypted local copies of your inventories, notes and drafts until you sign out or the sign-in ends.',
        ),
      ],
    },
  );

  add('logs', bi('Protokolle des Dienstes', 'Service logs'), {
    p: bi(
      'Die Schnittstelle schreibt strukturierte Protokolle mit Zeitpunkt, aufgerufenem Pfad, Status und einer Ablaufkennung. Einladungsgeheimnisse werden entfernt. Zur Begrenzung von Missbrauch wertet sie die Netzwerkadresse eines Aufrufs im Arbeitsspeicher aus. Die Hosting-Anbieter (siehe „Empfänger“) können eigene Zugriffsprotokolle führen. Grundlage: berechtigtes Interesse am sicheren Betrieb, Art. 6 Abs. 1 lit. f DSGVO.',
      'The API writes structured logs with time, requested path, status and a trace identifier. Invite secrets are removed. To limit abuse it evaluates the network address of a request in memory. The hosting providers (see "Recipients") can keep access logs of their own. Basis: legitimate interest in secure operation, Art. 6(1)(f) GDPR.',
    ),
  });

  add(
    'browser',
    bi('Speicher im Browser, Cookies, Tracking', 'Browser storage, cookies, tracking'),
    {
      p: bi(
        'Die Lorenzo-Apps setzen keine Cookies, binden keine Analyse-, Werbe- oder Tracking-Dienste ein und laden keine Schriftarten oder Skripte von Dritten. Sie speichern auf Ihrem Gerät nur Folgendes:',
        'The Lorenzo apps set no cookies, include no analytics, advertising or tracking services and load no fonts or scripts from third parties. They store only the following on your device:',
      ),
    },
    {
      table: {
        head: [
          bi('Schlüssel', 'Key'),
          bi('Speicher', 'Store'),
          bi('Wozu', 'What for'),
          bi('Wie lange', 'How long'),
        ],
        rows: STORAGE_KEYS.map((entry) => [
          same(entry.key),
          same(entry.store),
          entry.purpose,
          entry.lasts,
        ]),
      },
    },
  );

  add(
    'recipients',
    bi('Empfänger und Dienstleister', 'Recipients and service providers'),
    {
      p: bi(
        'Lorenzo nutzt die folgenden Anbieter. Der Betreiber hat Ort und Absicherung der Übermittlung bei den Anbietern erfragt und hier eingetragen.',
        'Lorenzo uses the following providers. The operator confirmed location and the safeguard for transfers with the providers and entered them here.',
      ),
    },
    {
      table: {
        head: [
          bi('Anbieter', 'Provider'),
          bi('Wozu', 'What for'),
          bi('Ort der Verarbeitung', 'Where it processes'),
          bi('Übermittlung außerhalb der EU', 'Transfer outside the EU'),
        ],
        rows: profile.providers.map((p) => [
          same(`${p.name} (${p.policyUrl})`),
          p.purpose,
          p.location,
          p.transfer,
        ]),
      },
    },
    {
      p: bi(
        'Außerdem werden Gravatar (einmalige Anfrage, siehe oben) und Discord (nur, wenn Sie den Bot nutzen) genannt; sie sind nicht Teil des normalen Betriebs der Web-Apps.',
        'Gravatar (a single request, see above) and Discord (only if you use the bot) are also named; they are not part of the normal operation of the web apps.',
      ),
    },
  );

  add('retention', bi('Speicherdauer', 'Retention'), {
    ul: [
      bi(
        'Konto und Inhalte: bis Sie das Konto löschen. Das Löschen entfernt Ihr Lorenzo-Konto, Ihre Mitgliedschaften, Spielerplätze und Rollen. Was Sie angelegt haben, bleibt in den Bibliotheken, ohne Sie als Urheber zu nennen. Im Aktivitätsprotokoll bleibt ein Vermerk mit der internen Kennung des gelöschten Kontos. Ihre Anmeldung bei Authgear wird dadurch nicht gelöscht; schreiben Sie uns, wenn auch sie entfernt werden soll.',
        'Account and content: until you delete your account. Deleting removes your Lorenzo account, memberships, player seats and roles. What you created stays in the libraries without naming you as its creator. The activity log keeps a note with the internal identifier of the deleted account. Your sign-in at Authgear is not deleted by this; write to us if it should be removed too.',
      ),
      bi(
        `Protokolle des Dienstes: ${profile.retention.logs.de}`,
        `Service logs: ${profile.retention.logs.en}`,
      ),
      bi(
        `Sicherungen: ${profile.retention.backups.de}`,
        `Backups: ${profile.retention.backups.en}`,
      ),
      bi(
        `Aktivitätsprotokoll einer Bibliothek: ${profile.retention.activityLog.de}`,
        `A library's activity log: ${profile.retention.activityLog.en}`,
      ),
      bi(
        'Daten auf Ihrem Gerät: bis zur Abmeldung oder bis Sie sie löschen.',
        'Data on your device: until you sign out or delete it.',
      ),
    ],
  });

  add(
    'rights',
    bi('Ihre Rechte', 'Your rights'),
    {
      p: bi(
        'Sie haben das Recht auf Auskunft (Art. 15 DSGVO), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung (Art. 18), Datenübertragbarkeit (Art. 20) und Widerspruch (Art. 21), und das Recht, sich bei einer Aufsichtsbehörde zu beschweren (Art. 77). Was Lorenzo dafür bietet:',
        'You have the right of access (Art. 15 GDPR), rectification (Art. 16), erasure (Art. 17), restriction (Art. 18), portability (Art. 20) and objection (Art. 21), and the right to complain to a supervisory authority (Art. 77). What Lorenzo offers for each:',
      ),
    },
    {
      ul: [
        bi(
          'Berichtigung: Sie ändern Ihre Profilangaben selbst im Profil.',
          'Rectification: you change your profile details yourself in your profile.',
        ),
        bi(
          'Löschung: im Profil können Sie Ihr Profilbild und Ihr Konto löschen, Bibliotheken verlassen und Token widerrufen. Das Löschen des Kontos braucht eine Anmeldung, kein Token.',
          'Erasure: in your profile you can delete your picture and your account, leave libraries and revoke tokens. Deleting the account needs a sign-in, not a token.',
        ),
        bi(
          'Auskunft und Übertragbarkeit: dafür gibt es noch keine Schaltfläche. Schreiben Sie uns; wir stellen Ihre Daten von Hand zusammen.',
          'Access and portability: there is no button for this yet. Write to us; we assemble your data by hand.',
        ),
        bi(
          'Widerspruch, Einschränkung: schreiben Sie uns.',
          'Objection, restriction: write to us.',
        ),
      ],
    },
    {
      p: bi(
        `Zuständige Aufsichtsbehörde: ${profile.supervisoryAuthority.name}, ${profile.supervisoryAuthority.url}. Eine Bereitstellung Ihrer Daten ist für die Nutzung der Konten nötig; automatisierte Entscheidungen oder Profiling finden nicht statt.`,
        `Competent supervisory authority: ${profile.supervisoryAuthority.name}, ${profile.supervisoryAuthority.url}. Providing your data is necessary to use accounts; there are no automated decisions or profiling.`,
      ),
    },
  );

  const support = profile.support;
  add('links', bi('Links auf fremde Seiten', 'Links to other sites'), {
    p: support
      ? bi(
          `Die Apps verlinken auf ${support.name} (${support.url}) und auf den Quellcode bei GitHub. Das sind Links: Es wird nichts eingebunden, und Ihr Browser wendet sich erst an diese Seiten, wenn Sie den Link öffnen.`,
          `The apps link to ${support.name} (${support.url}) and to the source code on GitHub. These are links: nothing is embedded, and your browser contacts those sites only when you open the link.`,
        )
      : bi(
          'Die Apps verlinken auf den Quellcode bei GitHub. Das ist ein Link: Es wird nichts eingebunden, und Ihr Browser wendet sich erst an GitHub, wenn Sie ihn öffnen.',
          'The apps link to the source code on GitHub. This is a link: nothing is embedded, and your browser contacts GitHub only when you open it.',
        ),
  });

  add(
    'changes',
    bi('Änderungen', 'Changes'),
    {
      p: bi(
        'Wenn sich ändert, was Lorenzo mit Daten tut, ändert sich diese Erklärung. Das Datum der letzten Änderung steht oben; der Verlauf liegt in der Versionsverwaltung des Projekts.',
        'When what Lorenzo does with data changes, this policy changes. The date of the last change is at the top; the history is in the project’s version control.',
      ),
    },
    {
      p: bi(
        'Der deutsche Text ist maßgeblich; die englische Fassung ist eine Übersetzung.',
        'The German text is binding; the English version is a translation.',
      ),
    },
  );

  return { title: bi('Datenschutzerklärung', 'Privacy policy'), sections };
}
