<!-- Thanks for contributing to Cairn. Please complete this checklist. -->

## What this changes
<!-- A clear description of the change and why. -->

## Checklist
- [ ] Tests pass locally (`pytest`) and cover the change.
- [ ] No secrets, credentials, or private data are committed.
- [ ] Each new module/branch traces to a design element (PLAN / spec / issue).
- [ ] If this touches detection/verification/routing: I considered the safety
      frames (does it work, could it harm good people, is it legal, is it
      auditable, is a human in the loop where required).
- [ ] Docs / CHANGELOG updated if behavior or interfaces changed.
- [ ] For any code that spawns a model/subprocess: it is isolated (no plugin/
      credential bleed) and fails closed.

## Related
<!-- Issues, design docs, prior PRs. -->
