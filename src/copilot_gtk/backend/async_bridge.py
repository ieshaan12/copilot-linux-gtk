# SPDX-License-Identifier: GPL-3.0-or-later
"""GLib ↔ asyncio event loop bridge for Copilot for GNOME.

This module provides helpers to integrate Python's asyncio with the GLib/GTK
main loop so that async SDK calls (copilot-sdk) run without blocking the UI.

The primary approach uses ``gbulb`` which replaces the default asyncio event
loop policy with one backed by the GLib main loop.

Usage in the application entry point::

    from copilot_gtk.backend.async_bridge import install_async_bridge, run_async

    # Call once before Gtk.Application.run()
    install_async_bridge()

    # Schedule async work from GTK callbacks
    run_async(some_coroutine())
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Coroutine
from typing import Any, TypeVar

import gi

gi.require_version('GLib', '2.0')
from gi.repository import GLib  # noqa: E402

log = logging.getLogger(__name__)

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None


def install_async_bridge() -> None:
    """Install the GLib-backed asyncio event loop policy.

    Must be called **once**, before ``Gtk.Application.run()`` or any
    ``asyncio.get_event_loop()`` call.  After this, all ``asyncio``
    primitives use the GLib main loop under the hood.
    """
    import gbulb

    gbulb.install(gtk=True)

    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    log.debug("GLib asyncio bridge installed (gbulb)")


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the GLib-backed asyncio event loop.

    Raises ``RuntimeError`` if :func:`install_async_bridge` has not been called.
    """
    if _loop is None:
        raise RuntimeError(
            "Async bridge not installed. Call install_async_bridge() first."
        )
    return _loop


def run_async(
    coro: Coroutine[Any, Any, T],
    callback: Any | None = None,
    error_callback: Any | None = None,
) -> asyncio.Task[T]:
    """Schedule an async coroutine on the GLib event loop.

    This is the main way GTK signal handlers should launch async work.
    The coroutine runs cooperatively on the GLib main loop — it will
    **not** block the UI.

    Args:
        coro: The coroutine to schedule.
        callback: Optional callable invoked with the result on success.
            Called on the main thread via ``GLib.idle_add``.
        error_callback: Optional callable invoked with the exception on failure.
            Called on the main thread via ``GLib.idle_add``.

    Returns:
        The ``asyncio.Task`` wrapping the coroutine.
    """
    loop = get_loop()
    task = loop.create_task(coro)

    def _on_done(t: asyncio.Task[T]) -> None:
        exc = t.exception()
        if exc is not None:
            log.error("Async task failed: %s\n%s", exc, "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ))
            if error_callback is not None:
                GLib.idle_add(error_callback, exc)
        else:
            if callback is not None:
                GLib.idle_add(callback, t.result())

    task.add_done_callback(_on_done)
    return task


def idle_add_async(coro: Coroutine[Any, Any, T]) -> None:
    """Convenience: schedule a coroutine from any thread via GLib.idle_add.

    Unlike :func:`run_async`, this is safe to call from a **non-main** thread.
    The coroutine will be created on the main thread inside a GLib idle callback.
    """

    def _schedule() -> bool:
        run_async(coro)
        return GLib.SOURCE_REMOVE

    GLib.idle_add(_schedule)
