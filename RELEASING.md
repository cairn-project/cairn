# Releasing cairn

> **Status: PROPOSED.** No formal release process exists in this repository
> yet. As of this writing the project has **no git tags**, **no CI/CD release
> workflow**, and **no published versions** — `git tag` returns nothing and
> there are no version/release/bump commits in the history. This document
> proposes a minimal, conventional process derived solely from
> `pyproject.toml` and the git history. Adopt, amend, or replace it before
> treating it as authoritative.

## What the build config tells us

Derived from `pyproject.toml`:

- **Build backend:** [`hatchling`](https://hatch.pypa.io/) (`build-system.requires = ["hatchling"]`, `build-backend = "hatchling.build"`).
- **Version source:** static — `project.version` is hard-coded (currently `0.1.0`). Hatch is *not* configured for VCS/tag-derived versioning, so the version is bumped by editing `pyproject.toml` directly.
- **Distribution name:** `cairn` — the project name is final; no rename pending.
- **Python support:** `requires-python = ">=3.11"`.
- **License:** MIT.
- **Console script:** `cairn = "cairn.cli:main"` (installs a `cairn` command).
- **Wheel contents:** the wheel packages `src/cairn` and force-includes non-Python data files — the spec (`spec/work_unit.schema.json`, `spec/SPEC.md`) and the JSON fixtures under `fixtures/`. These force-includes are load-bearing: a release built without them ships a broken package, so a built-artifact check (below) must confirm they are present.
- **Runtime dependency:** `jsonschema>=4.20`.
- **Dev dependency:** `pytest>=8.0` (optional-dependencies `dev`); tests live in `tests/` with `pythonpath = ["src"]`.

## Proposed release process

A standard "bump → tag → build → publish" flow for a static-version hatchling project.

### 1. Pre-flight

```sh
# Clean tree on the release branch, tests green.
git status --porcelain        # expect empty
pip install -e '.[dev]'
pytest
```

### 2. Bump the version

Edit `project.version` in `pyproject.toml` following [SemVer](https://semver.org/)
(`MAJOR.MINOR.PATCH`). While the project is pre-1.0 (`0.x`), breaking changes
bump the MINOR.

```sh
# e.g. 0.1.0 -> 0.2.0, edited by hand in pyproject.toml
git add pyproject.toml
git commit -m "release: v0.2.0"
```

### 3. Tag

Use an annotated tag, `v`-prefixed, matching `project.version` exactly.
(The repo has no tags today; this establishes the convention.)

```sh
git tag -a v0.2.0 -m "cairn v0.2.0"
git push origin main --follow-tags
```

### 4. Build

```sh
python -m pip install --upgrade build twine
python -m build            # produces dist/*.whl and dist/*.tar.gz via hatchling
```

Verify the wheel includes the force-included data files (spec + fixtures), since
a missing force-include yields a silently-broken package:

```sh
python -m zipfile -l dist/cairn-0.2.0-*.whl | grep -E 'spec/|fixtures/'
twine check dist/*
```

### 5. Publish

No publish target is configured in the repo, so pick one explicitly:

- **PyPI** (after confirming the `cairn` name is available on PyPI):

  ```sh
  twine upload dist/*
  ```

- **GitHub release** against the pushed tag (remote is
  `github.com/cairn-project/cairn`), attaching the `dist/` artifacts:

  ```sh
  gh release create v0.2.0 dist/* --title "cairn v0.2.0" --notes "..."
  ```

### 6. Post-release

- Confirm `pip install cairn==0.2.0` (or the GitHub artifact) installs and the
  `cairn` console script runs.
- Open the next development version if desired.

## Recommended hardening (not yet present)

- A CI workflow (`.github/workflows/ci.yml`) runs `pytest` on every push and
  pull request across Python 3.11–3.13. **(Done.)**
- Add a release workflow triggered on `v*` tags that builds and publishes,
  removing manual `twine`/`gh` steps.
- Consider `hatch-vcs` to derive `project.version` from the git tag, eliminating
  the manual `pyproject.toml` edit and keeping tag and version in lockstep.
- Confirm the `cairn` name is available on PyPI before the first public publish (the project name itself is final).
