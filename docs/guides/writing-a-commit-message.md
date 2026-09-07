# Writing a commit message

[Conventional Commits](https://www.conventionalcommits.org/), enforced by a commit-msg hook:

```text
<type>[optional scope]: <description>

[optional body]
```

Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `build`. Scope is usually the app: `feat(gm-console): ...`, `fix(loot-bot): ...`.

This isn't ceremony — release-please reads these to decide the next version number (`fix` → patch, `feat` → minor, a `BREAKING CHANGE:` footer or `!` → major) and to write the changelog entry. A vague message becomes a vague changelog line.

Good: `docs: add ADR for apps/ layout and multiplicity`
Bad: `updates`
