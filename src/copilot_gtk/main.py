# SPDX-License-Identifier: GPL-3.0-or-later
# Main entry point for Copilot for GNOME

import logging
import sys
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from .backend import CopilotService, install_async_bridge  # noqa: E402
from .window import CopilotWindow  # noqa: E402

log = logging.getLogger(__name__)


class CopilotGTKApplication(Adw.Application):
    """The main application class for Copilot for GNOME."""

    def __init__(self) -> None:
        super().__init__(
            application_id='io.github.ieshaan.CopilotGTK',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._service = CopilotService()
        self._window: CopilotWindow | None = None

    def do_startup(self) -> None:
        """Called once on app startup — load CSS, set up actions."""
        Adw.Application.do_startup(self)

        # Load custom stylesheet
        self._load_css()

        # Application-level actions
        self._setup_actions()

        # Install the gbulb async bridge
        install_async_bridge()

    def do_activate(self) -> None:
        """Called when the application is activated."""
        win = self.props.active_window
        if not win:
            win = CopilotWindow(
                service=self._service,
                application=self,
            )
            self._window = win

            # Start the Copilot SDK backend
            self._service.connect("ready", self._on_service_ready)
            self._service.connect("error", self._on_service_error)
            self._service.start()

        win.present()

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    def _load_css(self) -> None:
        """Load the custom CSS stylesheet."""
        css_path = Path(__file__).parent / "style.css"
        if css_path.exists():
            provider = Gtk.CssProvider()
            provider.load_from_path(str(css_path))
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            log.debug("Loaded CSS from %s", css_path)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _setup_actions(self) -> None:
        """Register application-level GActions."""
        about_action = Gio.SimpleAction(name="about")
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        prefs_action = Gio.SimpleAction(name="preferences")
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)

        quit_action = Gio.SimpleAction(name="quit")
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("win.new-chat", ["<Control>n"])

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_about(self, _action, _param) -> None:
        about = Adw.AboutDialog(
            application_name="Copilot for GNOME",
            application_icon="io.github.ieshaan.CopilotGTK",
            developer_name="ieshaan",
            version="0.1.0",
            developers=["ieshaan"],
            copyright="© 2026 ieshaan",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/ieshaan12/copilot-linux-gtk",
            issue_url="https://github.com/ieshaan12/copilot-linux-gtk/issues",
        )
        about.present(self._window)

    def _on_preferences(self, _action, _param) -> None:
        # Placeholder — will be implemented in Phase 5
        if self._window:
            self._window.show_toast("Preferences coming soon")

    def _on_quit(self, _action, _param) -> None:
        self._service.stop()
        self.quit()

    # ------------------------------------------------------------------
    # Service callbacks
    # ------------------------------------------------------------------

    def _on_service_ready(self, _service) -> None:
        log.info("Copilot SDK is ready")
        # Pre-fetch available models
        self._service.list_models()

    def _on_service_error(self, _service, message: str) -> None:
        log.error("Copilot SDK error: %s", message)


def main() -> int:
    """Application entry point."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s %(name)s: %(message)s",
    )
    app = CopilotGTKApplication()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
