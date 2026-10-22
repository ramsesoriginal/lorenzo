# Lorenzo Sessions

Lorenzo Sessions is where a GM prepares the sessions of a campaign and where players keep their notes on them. This guide is for game masters and players. Developers will find the implementation detail in [`apps/sessions/README.md`](../../apps/sessions/README.md); the decisions are in [RFC 0046](../rfcs/0046-sessions-scenes-and-lived-order.md) and [ADR 0317](../adr/0317-sessions-scenes-and-collaborative-planning.md) to [0319](../adr/0319-personal-lived-order-as-event-evidence.md).

## My sessions

The first page lists every session you are assigned to, as a GM or as a player, in any of your libraries. Each row gives the session's title, its real-world date (or "Date not set") and whether you are a GM or a player there. Choose a session to open it. A session you were not added to does not appear.

## Create a session

A GM of a campaign sees **Prepare a session** under the list. Give it a **Session title**, choose the **Campaign**, and optionally set a **Real-world date** and a **Link name** (the short name used in addresses and links). **Create session** opens the new session.

A session belongs to exactly one campaign. The GM who creates it is its first assigned GM, and its player roster starts empty.

## GMs and players

On the session page, assigned GMs open **GMs and players**:

- **GMs** are chosen from the campaign's GMs.
- **Players** are chosen from the campaign's players, and the **characters** each of them controls for this session are ticked separately beneath their name. Ticking a player does not tick any character.

**Save roster** stores the choice. If someone changed the roster meanwhile, **Review saved roster** shows what is saved without losing your selection.

The roster is only about who takes part in this session. It never changes campaign roles or who controls a character, and it does not turn a being into a Character. Non-player characters belong on a Scene's participant list, not here. A person removed from the roster loses the access the roster gave them; the roster is not a record of who attended.

## Real-world date and starting period

Under **Session details**, a GM can set the **Real-world date** and the **In-world starting period**. Both are optional while preparing. The real-world date is a calendar date, not a time of day, and it orders nothing. The starting period is chosen from calendar periods that already exist in the library; dates are created in [Lorenzo Calendars](calendars.md).

**Game time covered** lists the in-world periods the session covers. A GM ticks the periods and chooses **Save game time**. It is a set of periods, not a range: choosing the first and last day does not fill in the days between, and it is independent of the starting period and of the real-world date.

## Scenes and Scene appearances

A **Scene** is a reusable entry that belongs to no particular session. It can carry notes, an optional calendar period, and references (see below). **Browse reusable scenes** lists them and **Create a reusable scene** adds one; a Scene's own page has **Scene details** for its title, link name, **Visible in this library** and **Scene period**.

A **Scene appearance** is a Scene used inside a Session. Under **Add a scene**, a GM picks an existing Scene or creates one, and adds it to the session outline. The same Scene can appear in several sessions, and more than once in one.

The outline under **Scenes** is ordered. **Move up** and **Move down** reorder it. Each appearance is either **GM preparation** or shared with the session's participants, and **Share with session participants** or **Make preparation private** switches it. **Remove scene appearance** removes that appearance and the notes written on it, after confirmation; the reusable Scene stays.

A Scene and its appearance have separate audiences. Sharing an appearance with a session does not open a Scene that is restricted, and notes on an appearance belong to this group's session only. Notes on the Scene itself belong to every session that uses it.

## Notes

Anyone on the roster can add notes to the session and to its scene appearances, and edit their own. A note has a title, a **Note** (text and pictures, written in LorenzoScript) and an audience:

- **Me and Session GMs**: the author and the session's assigned GMs.
- **Session participants**: everyone on this session's roster.

Shared never means the whole library. Each note names its author, and a GM who can read a note is not thereby its author. Library administrators keep the access they already have. A GM of the campaign who is not assigned to the session does not gain access to its private notes, and a person removed from the roster loses theirs.

On a Scene's own page the two audiences read **Me and entry managers** and **Everyone in this library**.

## Facts, Events and beings

Sessions can refer to the entries they involve. A session shows **Direct session references** (Facts and Events), and a Scene shows **Scene references and participants** (Facts, Events and beings). A GM adds one with **Reference to add**, then **Add reference**.

Every reference starts as a **Private relationship**. **Share relationship** and **Make relationship private** change that, and **Remove reference** deletes it. A reader sees a reference only if they can see both ends of it, so sharing a reference never opens the Fact, Event or being it points to. A reference does not make a being a participant in an Event, and it does not record that anyone learned anything.

## Recorded play

**Recorded play** keeps what actually happened at the table apart from the preparation. Each scene appearance is **Planned**, **Played** or **Skipped**. A GM opens **Review and record played scenes**, sets the statuses and the played order (**Earlier in played order**, **Later in played order**), and saves with **Save played scenes**.

**Propose played order from preparation** fills in a draft: every scene not already skipped becomes played, in outline order. It is only a proposal; nothing is saved until the GM reviews it and saves. Preparation changes made afterwards do not alter the saved record, and play that was never recorded stays unrecorded.

Under each appearance, **Record Event presentation** notes that an Event was presented in that scene, with **Present earlier** and **Present later** for the order. The same Event can be presented in several scenes or sessions, which is how a flashback is recorded. Presentations start private, like references, and **Share presentation** opens them. Presenting an Event does not create it or change when it happened.

## Campaign session order

**Campaign session order** lists the campaign's sessions in an order that people chose, followed by the **Unplaced sessions** available to you. A GM can open **Edit order of sessions I manage**, then use **Move session earlier**, **Move session later**, **Leave session unplaced** and **Place session at end**, and finish with **Save session order**.

A GM reorders only the sessions they manage. The positions of other sessions stay as they are, and the list does not show positions among sessions you cannot see. Neither the date a session was created nor its real-world date sets the order.

## Personal lived order

Lived order is what one being experienced before what, which can differ from the order in which sessions presented it. A GM chooses a being under **Personal lived order** on the session page and opens **Review personal lived order**.

The page lists the being's Event participations already recorded, in alphabetical order rather than as a life sequence, and any lived-before evidence that exists. Someone allowed to order Events can record evidence with **Experienced earlier** and **Experienced later**, then **Save lived-before assertion**. **Share new lived evidence** is off unless ticked. As an alternative, **Propose from played participations** starts a draft from the Events presented in play; the GM reorders or leaves out participations and saves with **Save reviewed lived proposal**.

Evidence is private until shared. A set of assertions that would form a loop is refused. Saving never creates an Event participation, a cause or a learning record, and participations left out stay unplaced.

## What Sessions never infers

- A real-world date, a starting period or the time a note was written does not order anything.
- Preparation order, played order, campaign session order and lived order are four separate things, and none of them is worked out from another.
- A reference or a played scene does not mean a being took part in an Event, learned of it, or that it happened as shown.
- Sharing one thing never opens another: not an appearance's Scene, not a reference's target, not an Event's notes.
- Sessions has no "today" and no clock. It keeps no private text in the browser; only the appearance preference is remembered.
