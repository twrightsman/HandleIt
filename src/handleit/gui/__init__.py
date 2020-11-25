import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .application import HandleIt


def set_exception_hook(app):
    def new_hook(etype, evalue, etb):
        old_hook(etype, evalue, etb)
        # do stuff here
        while Gtk.main_level():
            Gtk.main_quit()
        sys.exit()

    old_hook = sys.excepthook
    sys.excepthook = new_hook


def main(version):
    app = HandleIt()
    set_exception_hook(app)

    return app.run(sys.argv)
