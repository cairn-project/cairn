"""Tests: the value-demo scenario (dump-for-review, NEVER send).

Covers the scenario's outcome-shaped acceptance criteria. The hermetic suite is
fully offline + deterministic: ``run_scenario(offline=True)`` uses deterministic
analysis nodes (no model, no network); the live-path AC injects a fake
``transcript_fn`` so no real ``claude -p`` is spawned.

  AC.SCN.1 (outcome-altitude)  the real entry point on a fresh ledger produces a
                               PENDING, not-routable finding + a banner-labeled
                               dump with evidence + resolved public recipient +
                               a draft, with no send.
  AC.SCN.2  a no-defect record produces no finding and no dump subdir (fail-quiet).
  AC.SCN.3  review flips PENDING→ROUTABLE only via a recorded human verdict; a
            reject with empty reason is refused; both log to the translog.
  AC.SCN.4  the run's transparency log passes verify_log.
  AC.SCN.5 (no-egress, structural)  no scenario module references a network-send
            surface; every dumped artefact carries the banner.
  AC.SCN.6  the org finder resolves only from the public registry and FAILS CLOSED
            on an unresolvable record (no recipient; dump says so).
  AC.SCN.7  the live (non-offline) path drives analysis through the claude adapter
            (mocked transcript) + the real verify quorum.
  AC.SCN.8  review accepts the truncated finding hashes the scenario's own
            run/list output prints (any unambiguous prefix >= 8 chars); the
            recorded verdict carries the FULL hash; too-short, unmatched, and
            ambiguous prefixes are all REFUSED (fail-closed).
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path

import pytest

import cairn.scenario as scenario_pkg
from cairn.ledger import FixedClock, Ledger, verify_log
from cairn.scenario import (
    REVIEW_BANNER,
    ReportingOrgFinder,
    classify_defect,
    list_scenario,
    review_scenario,
    run_scenario,
)
from cairn.scenario.dump import finding_dir
from cairn.scenario.runner import resolve_finding_prefix
from cairn.scenario.seed import classify_defect as _seed_classify
from cairn.vetting.review import VettingError

_KEY = b"scenario-test-key-not-secret"
_FIXED_TS = "2026-01-01T00:00:00+00:00"

# network-send surfaces the scenario must NEVER reference (the structural guard).
_FORBIDDEN_EGRESS = (
    "import socket",
    "import smtplib",
    "import requests",
    "urllib.request",
    "urlopen",
    "http.client",
    "httpx",
    ".sendmail(",
    "socket.socket(",
)


def _fresh_ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger", FixedClock(start=0.0), signing_key=_KEY)


# --- AC.SCN.1 (outcome-altitude) -------------------------------------------


def test_scn_1_offline_run_produces_pending_dump_no_send(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    review_dir = tmp_path / "review"
    summary = run_scenario(ledger, review_dir=review_dir, offline=True)

    # At least one flagged finding, all PENDING + not routable, nothing sent.
    assert summary.findings, "scenario produced no findings"
    assert summary.sent is False
    for f in summary.findings:
        assert f.state == "pending", f.to_dict()
        assert list_scenario(ledger)  # findings live in the real Gate-2 queue
        assert not ledger_is_routable(ledger, f.finding_hash)

    # At least one finding resolved a REAL public org recipient + a banner-labeled
    # dump with evidence + recipient + draft.
    resolved = [f for f in summary.findings if f.org_resolved]
    assert resolved, "no finding resolved a public reporting org"
    f = resolved[0]
    out = Path(f.dump_dir)
    md = (out / "packet.md").read_text(encoding="utf-8")
    pj = json.loads((out / "packet.json").read_text(encoding="utf-8"))
    prov = (out / "provenance.txt").read_text(encoding="utf-8")

    assert md.startswith(f"# {REVIEW_BANNER}")
    assert "Captured evidence" in md
    assert "DataGovHelp@gsa.gov" in md  # the real resolved public org inbox
    assert "Draft submission" in md
    assert pj["sent"] is False and pj["banner"] == REVIEW_BANNER
    assert pj["recipient"]["contact"] == "DataGovHelp@gsa.gov"
    assert "REAL" in prov and "no egress" in prov.lower()


def test_scn_1_via_cli_main(tmp_path):
    # The real CLI entry point, no pre-arranged state.
    from cairn.cli import main

    ledger_dir = tmp_path / "L"
    review_dir = tmp_path / "R"
    rc = main(
        [
            "scenario",
            "run",
            "--offline",
            "--ledger",
            str(ledger_dir),
            "--review-dir",
            str(review_dir),
            "--json",
        ]
    )
    assert rc == 0
    # a dump dir was written with a banner-labeled packet.
    dumps = list(review_dir.glob("*/packet.md"))
    assert dumps
    assert dumps[0].read_text(encoding="utf-8").startswith(f"# {REVIEW_BANNER}")


def ledger_is_routable(ledger: Ledger, finding_hash: str) -> bool:
    from cairn.vetting.finding_queue import FindingVetQueue

    return FindingVetQueue(ledger).is_routable(finding_hash)


# --- AC.SCN.2 (fail-quiet) --------------------------------------------------


def test_scn_2_no_defect_record_no_finding_no_dump(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    review_dir = tmp_path / "review"
    summary = run_scenario(ledger, review_dir=review_dir, offline=True)

    # the clean seed record produced no finding (fail-quiet) ...
    assert "city-bike-counts-2019-2023" in summary.no_defect_records
    flagged_records = {f.record_id for f in summary.findings}
    assert "city-bike-counts-2019-2023" not in flagged_records
    # ... and exactly one dump subdir per flagged finding (none for the clean one).
    subdirs = [p for p in review_dir.iterdir() if p.is_dir()]
    assert len(subdirs) == len(summary.findings)


# --- AC.SCN.3 (human gate) --------------------------------------------------


def test_scn_3_review_flips_routable_only_via_human_verdict(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    summary = run_scenario(ledger, review_dir=tmp_path / "review", offline=True)
    target = next(f for f in summary.findings if f.org_resolved)

    # PENDING until a human records a verdict.
    assert not ledger_is_routable(ledger, target.finding_hash)
    result = review_scenario(
        ledger,
        target.finding_hash,
        routable=True,
        reason="verified benign 404; ok to consider",
        reviewer_id="reviewer-1",
    )
    assert result.state == "routable"
    assert ledger_is_routable(ledger, target.finding_hash)

    # the verdict logged to the same transparency log.
    kinds = [e.kind for e in ledger.translog.entries()]
    assert "FINDING_VET_VERDICT" in kinds


def test_scn_3_reject_empty_reason_refused(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    summary = run_scenario(ledger, review_dir=tmp_path / "review", offline=True)
    target = summary.findings[0]
    with pytest.raises(VettingError):
        review_scenario(
            ledger,
            target.finding_hash,
            routable=False,
            reason="   ",
            reviewer_id="reviewer-1",
        )
    # still PENDING — no silent rejection.
    assert not ledger_is_routable(ledger, target.finding_hash)


# --- AC.SCN.4 (auditable) ---------------------------------------------------


def test_scn_4_transparency_log_verifies(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    summary = run_scenario(ledger, review_dir=tmp_path / "review", offline=True)
    v = verify_log(tmp_path / "ledger" / "translog.jsonl")
    assert v.ok is True
    assert v.head_hash == summary.log_head


# --- AC.SCN.5 (no-egress, structural) ---------------------------------------


def test_scn_5_no_egress_surface_in_scenario_package():
    pkg_dir = Path(scenario_pkg.__file__).parent
    for mod in pkgutil.iter_modules([str(pkg_dir)]):
        source = (pkg_dir / f"{mod.name}.py").read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_EGRESS:
            assert forbidden not in source, (
                f"scenario.{mod.name} references a network-send surface "
                f"{forbidden!r} — the scenario must have NO egress code path"
            )
    # the package itself imports cleanly with no egress import.
    src = (pkg_dir / "__init__.py").read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_EGRESS:
        assert forbidden not in src


def test_scn_5_every_dumped_artefact_carries_banner(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    review_dir = tmp_path / "review"
    summary = run_scenario(ledger, review_dir=review_dir, offline=True)
    assert summary.findings
    for f in summary.findings:
        out = Path(f.dump_dir)
        assert (out / "packet.md").read_text(encoding="utf-8").splitlines()[0] == (
            f"# {REVIEW_BANNER}"
        )
        assert json.loads((out / "packet.json").read_text())["banner"] == REVIEW_BANNER
        assert (out / "provenance.txt").read_text().startswith(REVIEW_BANNER)


# --- AC.SCN.6 (org finder public-only / fail-closed) ------------------------


def test_scn_6_finder_resolves_public_org_only_and_fails_closed():
    finder = ReportingOrgFinder()
    # a data.gov-steward record resolves the public org inbox.
    resolved = finder.resolve({"steward": "data.gov"})
    assert resolved is not None
    assert resolved.contact == "DataGovHelp@gsa.gov"
    assert resolved.is_public_org is True
    # an unknown steward FAILS CLOSED — no guessed/private recipient.
    assert finder.resolve({"steward": "unknown"}) is None
    assert finder.resolve({"steward": ""}) is None
    assert finder.resolve({"steward": "some-unlisted-agency"}) is None


def test_scn_6_unresolvable_record_dump_says_no_contact(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    review_dir = tmp_path / "review"
    summary = run_scenario(ledger, review_dir=review_dir, offline=True)
    orphan = next(f for f in summary.findings if not f.org_resolved)
    assert orphan.recipient_contact is None
    md = (Path(orphan.dump_dir) / "packet.md").read_text(encoding="utf-8")
    assert "No public contact resolved; do not proceed" in md
    pj = json.loads((Path(orphan.dump_dir) / "packet.json").read_text())
    assert pj["recipient"] == {} and pj["draft_submission"] is None


# --- AC.SCN.7 (real-AI path, mocked transcript) -----------------------------


def _fake_claude(prompt: str) -> str:
    """Honest fake: parse the inputs from the rendered prompt + apply the rule."""
    inputs_section = prompt.split("INPUTS:", 1)[1]
    blob = inputs_section.split("\n\n", 1)[0].strip()
    inputs = json.loads(blob)
    meta = inputs.get("inline", {}).get("registration_metadata", {})
    return json.dumps(classify_defect({"registration_metadata": meta}))


def test_scn_7_live_path_drives_claude_adapter(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    review_dir = tmp_path / "review"
    summary = run_scenario(
        ledger,
        review_dir=review_dir,
        offline=False,
        transcript_fn=_fake_claude,
        clock_fn=lambda: _FIXED_TS,
    )
    # the live claude family participates in the accepted quorum for findings.
    assert summary.offline is False
    assert summary.findings
    for f in summary.findings:
        pj = json.loads((Path(f.dump_dir) / "packet.json").read_text())
        assert "claude" in pj["quorum_families"]
    # provenance records the REAL live analysis path.
    prov = (Path(summary.findings[0].dump_dir) / "provenance.txt").read_text()
    assert "live claude -p" in prov
    assert verify_log(tmp_path / "ledger" / "translog.jsonl").ok is True


# --- AC.SCN.8 (review accepts the hashes its own output prints) --------------


def test_scn_8_review_accepts_truncated_hashes_run_and_list_print(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    summary = run_scenario(ledger, review_dir=tmp_path / "review", offline=True)
    assert len(summary.findings) >= 2, "need two findings to cover both printed widths"
    first, second = summary.findings[0], summary.findings[1]

    # `scenario run` prints hash[:12]; `scenario list` prints hash[:16].
    result = review_scenario(
        ledger,
        first.finding_hash[:12],
        routable=True,
        reason="verified benign",
        reviewer_id="reviewer-1",
    )
    # the recorded verdict carries the FULL hash, never the prefix.
    assert result.finding_hash == first.finding_hash
    assert ledger_is_routable(ledger, first.finding_hash)

    result = review_scenario(
        ledger,
        second.finding_hash[:16],
        routable=True,
        reason="verified benign",
        reviewer_id="reviewer-1",
    )
    assert result.finding_hash == second.finding_hash
    assert ledger_is_routable(ledger, second.finding_hash)


def test_scn_8_unmatched_prefix_refused_and_nothing_recorded(tmp_path):
    ledger = _fresh_ledger(tmp_path)
    summary = run_scenario(ledger, review_dir=tmp_path / "review", offline=True)
    with pytest.raises(VettingError, match="not in the finding-vet queue"):
        review_scenario(
            ledger,
            "deadbeef0000",
            routable=True,
            reason="x",
            reviewer_id="reviewer-1",
        )
    for f in summary.findings:  # every finding still PENDING — fail-closed.
        assert not ledger_is_routable(ledger, f.finding_hash)


def test_scn_8_prefix_resolution_fails_closed():
    shared = "a1b2c3d4"
    candidates = [shared + "0" * 56, shared + "f" * 56]

    # ambiguous prefix → refused, both matches named.
    with pytest.raises(VettingError, match="ambiguous"):
        resolve_finding_prefix(candidates, shared)
    # one more character disambiguates.
    assert resolve_finding_prefix(candidates, shared + "0") == candidates[0]
    # shorter than the 8-char floor → refused even if it would be unique.
    with pytest.raises(VettingError, match="too short"):
        resolve_finding_prefix(candidates, shared[:7])
    # a full-length hash is passed through UNCHANGED (never prefix-matched),
    # even when it matches nothing — existence stays the gate's decision.
    unknown = "e" * 64
    assert resolve_finding_prefix(candidates, unknown) == unknown


# --- sanity on the shared rule ----------------------------------------------


def test_classify_defect_rule_is_shared_and_deterministic():
    assert classify_defect is _seed_classify
    assert classify_defect({"registration_metadata": {"download_status": 404}})["has_defect"]
    assert classify_defect({"registration_metadata": {"license_field": ""}})["has_defect"]
    clean = classify_defect(
        {"registration_metadata": {"download_status": 200, "license_field": "MIT"}}
    )
    assert clean["has_defect"] is False and clean["defect_confidence"] == 0.0


def test_finding_dir_short_hash():
    p = finding_dir(Path("/x"), "abcdef0123456789")
    assert p.name == "abcdef012345"


def test_scenario_modules_importable():
    # every submodule imports cleanly (no syntax / circular issues).
    pkg_dir = Path(scenario_pkg.__file__).parent
    for mod in pkgutil.iter_modules([str(pkg_dir)]):
        importlib.import_module(f"cairn.scenario.{mod.name}")
