from typing import List

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")

from gi.repository import Gtk, Gio, Gdk, Handy

from .window import HandleItWindow


class HandleIt(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.wrightsman.HandleIt",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

        # add in custom icons
        dit = Gtk.IconTheme.get_default()
        dit.add_resource_path("/org/wrightsman/HandleIt/icons")

        # load application stylesheet
        default_css = Gtk.CssProvider()
        default_css.load_from_resource("/org/wrightsman/HandleIt/style/default.css")
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            default_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def do_startup(self):
        # super does not work here yet, see https://gitlab.gnome.org/GNOME/pygobject/-/issues/58
        Gtk.Application.do_startup(self)
        Handy.init()

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = HandleItWindow(application=self)

        win.show_all()
        win.present()
