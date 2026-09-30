"""A healthy previous deployment must never accept a new renderer release."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_probe", ROOT / "scripts/ci/wait_for_render_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def clock(monkeypatch):
    now = [0]
    monkeypatch.setattr(release.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(release.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))


@pytest.mark.parametrize("response", [
    (200, {"status": "healthy", "render_revision": "old"}),
    (200, {"status": "healthy"}),
    (503, {"status": "unhealthy", "render_revision": "new"}),
    (200, {}),
    (200, []),
])
def test_old_or_unready_backend_cannot_accept_new_release(monkeypatch, clock, response):
    monkeypatch.setattr(release, "probe", lambda *_: response)
    assert release.wait_for_release("https://example.test/ready", "new", timeout=2, interval=1) == 1


def test_rollout_transport_failure_then_old_then_new(monkeypatch, clock):
    probe = Mock(side_effect=[ValueError("502 HTML"),
                             (200, {"status": "healthy", "render_revision": "old"}),
                             (200, {"status": "healthy", "render_revision": "new"})])
    monkeypatch.setattr(release, "probe", probe)
    assert release.wait_for_release("https://example.test/ready", "new", timeout=3, interval=1) == 0
    assert probe.call_count == 3


def test_frontend_only_publish_checks_availability(monkeypatch, clock):
    monkeypatch.setattr(release, "probe", lambda *_: (200, {"status": "healthy", "render_revision": "old"}))
    assert release.wait_for_release("https://example.test/ready", "") == 0


def test_workflow_uses_same_identity_for_build_and_verification():
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text())
    jobs = workflow["jobs"]
    verify = jobs["verify-deploy"]
    assert "build-backend" in verify["needs"]
    build = next(s for s in jobs["build-backend"]["steps"] if s.get("name") == "Build and push")
    step = next(s for s in verify["steps"] if s.get("name") == "Wait for the serving renderer release")
    assert "RENDER_BUILD_ID=" + step["env"]["RENDER_BUILD_ID"] in build["with"]["build-args"]
    assert '--expected-revision "$EXPECTED"' in step["run"]
    assert '"$BACKEND_RESULT" = success' in step["run"]
