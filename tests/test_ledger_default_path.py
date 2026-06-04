"""Default-ledger resolution: the cause-flow commands persist to a stable
default ledger so a multi-step flow "just works" without threading --ledger.

Resolution order (verified here):
  1. explicit --ledger arg            -> that path, verbatim
  2. $CAIRN_LEDGER env var            -> that path
  3. $XDG_DATA_HOME/cairn/ledger      -> if XDG_DATA_HOME set
  4. ~/.local/share/cairn/ledger      -> final fallback

The resolver creates the directory it returns (so the first command on a
fresh machine succeeds), and returns the SAME path on a second call with the
same environment (the persistence property the cause flow depends on).
"""

from __future__ import annotations

from cairn.cli import resolve_ledger_dir


def test_explicit_arg_wins_over_everything(tmp_path, monkeypatch):
    monkeypatch.setenv("CAIRN_LEDGER", str(tmp_path / "env"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    explicit = tmp_path / "explicit"
    got = resolve_ledger_dir(str(explicit))
    assert got == explicit


def test_env_var_used_when_no_arg(tmp_path, monkeypatch):
    env_dir = tmp_path / "env-ledger"
    monkeypatch.setenv("CAIRN_LEDGER", str(env_dir))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    got = resolve_ledger_dir(None)
    assert got == env_dir
    assert got.is_dir()  # resolver creates it


def test_xdg_data_home_used_when_no_arg_no_env(tmp_path, monkeypatch):
    monkeypatch.delenv("CAIRN_LEDGER", raising=False)
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    got = resolve_ledger_dir(None)
    assert got == xdg / "cairn" / "ledger"
    assert got.is_dir()


def test_home_fallback_when_no_arg_no_env_no_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("CAIRN_LEDGER", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    got = resolve_ledger_dir(None)
    assert got == tmp_path / "home" / ".local" / "share" / "cairn" / "ledger"
    assert got.is_dir()


def test_resolution_is_stable_across_calls(tmp_path, monkeypatch):
    """The persistence property: same env -> same path twice (no fresh temp dir)."""
    monkeypatch.delenv("CAIRN_LEDGER", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    first = resolve_ledger_dir(None)
    second = resolve_ledger_dir(None)
    assert first == second


def test_explicit_arg_path_not_required_to_preexist(tmp_path):
    """An explicit --ledger to a not-yet-existing dir is returned verbatim;
    the Ledger constructor creates its own structure underneath."""
    target = tmp_path / "does-not-exist-yet"
    got = resolve_ledger_dir(str(target))
    assert got == target
