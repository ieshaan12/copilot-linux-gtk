# SPDX-License-Identifier: GPL-3.0-or-later
# Main entry point for Copilot for GNOME

import sys

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, Gtk  # noqa: E402


class CopilotGTKApplication(Adw.Application):
    """The main application class for Copilot for GNOME."""

    def __init__(self) -> None:
        super().__init__(
            application_id='io.github.ieshaan.CopilotGTK',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self) -> None:
        """Called when the application is activated."""
        win = self.props.active_window
        if not win:
            win = Adw.ApplicationWindow(application=self)
            win.set_default_size(900, 600)
            win.set_title('Copilot for GNOME')

            # Wrap content in an Adw.ToolbarView with a HeaderBar
            toolbar_view = Adw.ToolbarView()
            header_bar = Adw.HeaderBar()
            toolbar_view.add_top_bar(header_bar)

            # Empty status page as initial content
            status_page = Adw.StatusPage()
            status_page.set_title('Copilot for GNOME')
            status_page.set_description('Your AI assistant for the GNOME desktop')
            status_page.set_icon_name('dialog-information-symbolic')
            toolbar_view.set_content(status_page)

            win.set_content(toolbar_view)

        win.present()


def main() -> int:
    """Application entry point."""
    app = CopilotGTKApplication()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
