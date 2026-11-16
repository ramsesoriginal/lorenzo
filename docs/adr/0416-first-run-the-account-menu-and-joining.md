# 0416 - First run, the account menu and joining

Status: accepted, decided with the maintainer on 2026-11-04. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web](../design/web/README.md), D27.

## Context

A new account has no library, and the ways out (set one up, join one, look around) are spread over several pages.

## Decision

- **First run** for an account with no library: two doors on one screen, "I run a game" (set up a library) and "I'm joining a game" (an invite link field), with the mascot image `first-run-welcome`. The word is **library**: "Set up a library". "Just looking around" (browse public repositories) is hidden when public repositories are off. An account with an invite pending sees the joining page, and first run appears only when there is neither a library nor an invite.
- **The account menu** holds Profile, Notifications, Libraries and people, Access tokens and devices, Appearance, Keyboard shortcuts and Sign out. Signing out with unsent changes says plainly what is only on the device and what happens to it.
- **Joining** has four moments: a preview signed out, a preview signed in, done, and one message for every link that does not work (unknown, expired, revoked and used up all read "This link doesn't work any more").

## Consequences

- The pages the account menu opens are in [ADR 0417](0417-account-hub-redesign.md) and [ADR 0418](0418-profile-access-tokens-and-connecting-a-device.md).
- A link's state is never told apart from outside, so a guessed link learns nothing.
