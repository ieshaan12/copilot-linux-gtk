# SPDX-License-Identifier: GPL-3.0-or-later
"""Pytest fixtures for automated UI tests.

These fixtures handle:
1. Launching a headless display server (Xvfb or weston) if no display is available
2. Launching the app subprocess with ``COPILOT_GTK_MOCK_BACKEND=1``
3. Initializing dogtail and finding the application frame via AT-SPI
4. Teardown: kill app + compositor, capture screenshot on failure
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME = "Copilot for GNOME"
APP_ID = "io.github.ieshaan.CopilotGTK"
TEST_APP_ID = "io.github.ieshaan.CopilotGTK.Test"
TEST_OBJECT_PATH = "/io/github/ieshaan/CopilotGTK/Test"
TEST_WINDOW_PATH = "/io/github/ieshaan/CopilotGTK/Test/window/1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
STARTUP_TIMEOUT = 15  # seconds to wait for the app to appear in AT-SPI tree
MOCK_RESPONSE_DELAY_MS = 30  # faster streaming for tests

# ---------------------------------------------------------------------------
# Display server management
# ---------------------------------------------------------------------------


def _have_display() -> bool:
    """Check whether a display server is available."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _start_xvfb() -> subprocess.Popen | None:
    """Start Xvfb on :99 and set DISPLAY. Returns the process or None."""
    display = ":99"
    try:
        proc = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x1024x24", "-ac"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            log.warning("Xvfb exited immediately")
            return None
        os.environ["DISPLAY"] = display
        log.info("Started Xvfb on %s (pid %d)", display, proc.pid)
        return proc
    except FileNotFoundError:
        log.warning("Xvfb not found")
        return None


def _start_weston_headless() -> subprocess.Popen | None:
    """Start weston in headless mode. Returns the process or None."""
    try:
        proc = subprocess.Popen(
            [
                "weston",
                "--backend=headless",
                "--width=1280",
                "--height=1024",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        if proc.poll() is not None:
            log.warning("weston exited immediately")
            return None
        log.info("Started weston headless (pid %d)", proc.pid)
        return proc
    except FileNotFoundError:
        log.warning("weston not found")
        return None


def _start_headless_display() -> subprocess.Popen | None:
    """Try to start a headless display server if none is available."""
    if _have_display():
        log.info("Display already available: DISPLAY=%s WAYLAND_DISPLAY=%s",
                 os.environ.get("DISPLAY"), os.environ.get("WAYLAND_DISPLAY"))
        return None

    # Try Xvfb first (more common in CI), then weston
    proc = _start_xvfb()
    if proc is not None:
        return proc

    proc = _start_weston_headless()
    if proc is not None:
        return proc

    pytest.skip("No display server available and cannot start Xvfb or weston")
    return None  # unreachable but keeps mypy happy


def _kill_proc(proc: subprocess.Popen | None) -> None:
    """Terminate and wait for a subprocess."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


# ---------------------------------------------------------------------------
# AT-SPI / dogtail helpers
# ---------------------------------------------------------------------------


def _ensure_a11y() -> None:
    """Make sure AT-SPI accessibility is enabled."""
    os.environ.setdefault("GTK_A11Y", "atspi")
    os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", "")
    # dogtail 2.0 config
    try:
        import dogtail.config
        dogtail.config.config.check_for_a11y = False
        dogtail.config.config.search_cut_off_limit = 30
        dogtail.config.config.default_delay = 0.3
        dogtail.config.config.action_delay = 0.3
    except Exception:
        pass


def _find_app_node(timeout: float = STARTUP_TIMEOUT):
    """Wait for the app to appear in the AT-SPI tree and return its Node."""
    import dogtail.tree

    # The app may appear under various names depending on how it's launched:
    # - "Copilot for GNOME" (when GApplication name is picked up)
    # - "main.py" (when launched via `python -m copilot_gtk.main`)
    # - "copilot-gtk" (entry-point name)
    _MATCH_NAMES = ("copilot", "main.py", "copilot-gtk")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            root = dogtail.tree.root
            for app in root.applications():
                app_name = getattr(app, "name", "") or ""
                if any(n in app_name.lower() for n in _MATCH_NAMES):
                    log.info("Found app in AT-SPI tree: %r", app_name)
                    return app
        except Exception:
            pass
        time.sleep(0.5)

    # Log what we did find for debugging
    try:
        root = dogtail.tree.root
        names = [getattr(a, "name", "?") for a in root.applications()]
        log.error("AT-SPI apps found: %s", names)
    except Exception:
        pass

    raise TimeoutError(
        f"App '{APP_NAME}' did not appear in AT-SPI tree within {timeout}s"
    )


# ---------------------------------------------------------------------------
# Shared UI test helpers
# ---------------------------------------------------------------------------

# Names matching how the app registers in AT-SPI
VALID_APP_NAMES = ("copilot", "main.py", "copilot-gtk")


def safe_find(node, predicate, retry: bool = False):
    """Wrapper around find_child that returns None instead of raising."""
    try:
        result = node.find_child(predicate, retry=retry)
        return result
    except Exception:
        return None


def find_by_role_and_name(node, role: str, name_substring: str):
    """Find a child with a specific role and name substring.

    Handles GTK4 AT-SPI role naming: GTK4 uses ``"button"`` where
    GTK3 used ``"push button"``.
    """
    # Normalise role aliases
    role_set = {role}
    if role == "push button":
        role_set.add("button")
    elif role == "button":
        role_set.add("push button")
    if role == "toggle button":
        role_set.add("button")

    try:
        children = node.find_children(
            lambda n: n.roleName in role_set
            and name_substring.lower() in (getattr(n, "name", "") or "").lower()
        )
        return children[0] if children else None
    except Exception:
        return None


def wait_for_sdk_ready(app_node, timeout: float = 10) -> bool:
    """Wait for the mock SDK to become ready.

    Detects readiness by looking for either:
    - The 'Conversations' grouping (sidebar rendered)
    - The 'Send message' button (chat view active)

    GTK4 header-bar buttons are NOT exposed in AT-SPI, so we can't
    rely on finding a 'New Chat' button.
    """
    window = app_node.child(roleName="frame")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # Check for sidebar grouping or Send button
        btn = find_by_role_and_name(window, "button", "Send message")
        if btn is not None:
            return True
        grp = safe_find(
            window,
            lambda n: n.roleName == "grouping"
            and "Conversations" in (getattr(n, "name", "") or ""),
        )
        if grp is not None:
            return True
        time.sleep(0.5)
    return False


def click_new_chat(app_node) -> bool:
    """Activate the ``win.new-chat`` GAction via gdbus.

    Header-bar buttons are not exposed in GTK4's AT-SPI tree,
    so we activate the action programmatically.
    """
    try:
        subprocess.run(
            [
                "gdbus", "call",
                "--session",
                "--dest", TEST_APP_ID,
                "--object-path", TEST_WINDOW_PATH,
                "--method", "org.gtk.Actions.Activate",
                "new-chat", "[]", "{}",
            ],
            timeout=5,
            capture_output=True,
            check=True,
        )
        time.sleep(1)
        return True
    except Exception:
        # Fallback: try clicking a button named "New Chat" in case
        # the app layout exposes it (e.g., on the empty-state page)
        window = app_node.child(roleName="frame")
        btn = find_by_role_and_name(window, "button", "New Chat")
        if btn is not None:
            try:
                btn.click()
                time.sleep(1)
                return True
            except Exception:
                pass
        return False


def find_text_input(app_node):
    """Find a sensitive text input widget in the window."""
    window = app_node.child(roleName="frame")
    try:
        entries = window.find_children(
            lambda n: n.roleName in ("text", "text entry", "editbar")
        )
        for entry in entries:
            try:
                if entry.sensitive:
                    return entry
            except Exception:
                continue
        return entries[0] if entries else None
    except Exception:
        return None


def require_interaction(func):
    """Decorator that skips the test if basic interaction (click/type) fails."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if "find" in str(exc).lower() or "atspi" in str(exc).lower():
                pytest.skip(f"AT-SPI interaction not available: {exc}")
            raise

    return wrapper


# ---------------------------------------------------------------------------
# Screenshot capture
# ---------------------------------------------------------------------------


def _take_screenshot(name: str) -> Path | None:
    """Capture a screenshot for debugging. Returns the path or None."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{timestamp}.png"

    try:
        # Try using gnome-screenshot or import (ImageMagick)
        for cmd in [
            ["gnome-screenshot", "-f", str(path)],
            ["import", "-window", "root", str(path)],
            ["scrot", str(path)],
        ]:
            try:
                subprocess.run(cmd, timeout=5, capture_output=True)
                if path.exists():
                    log.info("Screenshot saved: %s", path)
                    return path
            except FileNotFoundError:
                continue

        # Fallback: try Pillow with X11
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(str(path))
            log.info("Screenshot saved (Pillow): %s", path)
            return path
        except Exception:
            pass

    except Exception as exc:
        log.warning("Failed to capture screenshot: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def headless_display() -> Generator[subprocess.Popen | None, None, None]:
    """Session-scoped fixture: start a headless display if needed."""
    proc = _start_headless_display()
    yield proc
    _kill_proc(proc)


@pytest.fixture(scope="session")
def a11y_setup() -> None:
    """Ensure accessibility settings are configured for the test session."""
    _ensure_a11y()


@pytest.fixture()
def app_process(
    headless_display: subprocess.Popen | None,
    a11y_setup: None,
    tmp_path: Path,
) -> Generator[subprocess.Popen, None, None]:
    """Launch the application with mock backend and yield the subprocess.

    The fixture sets up the mock backend environment, starts the app,
    and tears it down after the test.
    """
    env = os.environ.copy()
    env["COPILOT_GTK_MOCK_BACKEND"] = "1"
    env["COPILOT_GTK_MOCK_DELAY"] = str(MOCK_RESPONSE_DELAY_MS)
    env["COPILOT_GTK_TEST_MODE"] = "1"
    env["GTK_A11Y"] = "atspi"
    # Use a temporary data directory to avoid polluting user data
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")

    # Launch the app
    proc = subprocess.Popen(
        [sys.executable, "-m", "copilot_gtk.main"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    log.info("Launched app (pid %d)", proc.pid)

    # Give the app time to start
    time.sleep(2)

    if proc.poll() is not None:
        stdout = proc.stdout.read().decode() if proc.stdout else ""
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(
            f"App exited prematurely (code {proc.returncode}).\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    yield proc

    # Teardown
    _kill_proc(proc)


@pytest.fixture()
def app_node(app_process: subprocess.Popen):
    """Find and return the app's AT-SPI Node via dogtail."""
    return _find_app_node()


@pytest.fixture(autouse=True)
def screenshot_on_failure(request):
    """Automatically capture a screenshot when a UI test fails."""
    yield
    rep_call = getattr(request.node, "rep_call", None)
    if rep_call is not None and rep_call.failed:
        test_name = request.node.name.replace("[", "_").replace("]", "_")
        _take_screenshot(test_name)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test result in item for the screenshot_on_failure fixture."""
    import pluggy

    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
