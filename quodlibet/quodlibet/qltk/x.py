# -*- coding: utf-8 -*-
# Copyright 2005 Joe Wreschnig, Michael Urman
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation

# Things that are more or less direct wrappers around GTK widgets to
# ease constructors.

from gi.repository import Gtk, GObject, GLib, Gio

from quodlibet import util
from quodlibet import config
from quodlibet.qltk import add_css, is_accel, gtk_version


class ScrolledWindow(Gtk.ScrolledWindow):
    """Draws a border around all edges that don't touch the parent window"""

    def do_size_allocate(self, alloc):
        if self.get_shadow_type() == Gtk.ShadowType.NONE:
            return Gtk.ScrolledWindow.do_size_allocate(self, alloc)

        toplevel = self.get_toplevel()
        # try to get the child so we ignore the CSD
        toplevel = toplevel.get_child() or toplevel

        try:
            dx, dy = self.translate_coordinates(toplevel, 0, 0)
        except TypeError:
            GLib.idle_add(self.queue_resize)
            return Gtk.ScrolledWindow.do_size_allocate(self, alloc)

        ctx = self.get_style_context()
        border = ctx.get_border(ctx.get_state())

        # https://bugzilla.gnome.org/show_bug.cgi?id=694844
        border.left = border.top = border.right = border.bottom = 1

        # XXX: ugly, ugly hack
        # Pretend the main window toolbar is the top of the window.
        # This removes the top border in case the ScrolledWindow
        # is drawn right below the toolbar.
        try:
            top_bar = toplevel.top_bar
            if not isinstance(top_bar, Gtk.Widget):
                raise TypeError
        except (AttributeError, TypeError):
            pass
        else:
            top_ctx = top_bar.get_style_context()
            b = top_ctx.get_border(top_ctx.get_state())
            if b.bottom:
                dy_bar = self.translate_coordinates(top_bar, 0, 0)[1]
                dy_bar -= top_bar.get_allocation().height
                dy = min(dy, dy_bar)

        # since 3.15 the gdkwindow moves to dx==-1 with the allocation
        # so ignore anything < 0 (I guess something passes the adjusted alloc
        # to us a second time)
        # https://git.gnome.org/browse/gtk+/commit/?id=fdf367e8689cb
        dx = max(0, dx)
        dy = max(0, dy)

        # Don't remove the border if the border is drawn inside
        # and the scrollbar on that edge is visible
        bottom = left = right = top = False

        value = GObject.Value()
        value.init(GObject.TYPE_BOOLEAN)
        # default to True: https://bugzilla.gnome.org/show_bug.cgi?id=701058
        value.set_boolean(True)
        ctx.get_style_property("scrollbars-within-bevel", value)
        scroll_within = value.get_boolean()
        value.unset()

        if not scroll_within:
            h, v = self.get_hscrollbar(), self.get_vscrollbar()
            hscroll = vscroll = False
            if h.get_visible():
                req = h.size_request()
                hscroll = bool(req.width + req.height)

            if v.get_visible():
                req = v.size_request()
                vscroll = bool(req.width + req.height)

            placement = self.get_placement()
            if placement == Gtk.CornerType.TOP_LEFT:
                bottom = hscroll
                right = vscroll
            elif placement == Gtk.CornerType.BOTTOM_LEFT:
                right = vscroll
                top = hscroll
            elif placement == Gtk.CornerType.TOP_RIGHT:
                bottom = hscroll
                left = vscroll
            elif placement == Gtk.CornerType.BOTTOM_RIGHT:
                left = vscroll
                top = hscroll

        top_alloc = toplevel.get_allocation()
        width, height = top_alloc.width, top_alloc.height
        if alloc.height + dy == height and not bottom:
            alloc.height += border.bottom

        if alloc.width + dx == width and not right:
            alloc.width += border.right

        if dy == 0 and not top:
            alloc.y -= border.top
            alloc.height += border.top

        if dx == 0 and not left:
            alloc.x -= border.left
            alloc.width += border.left

        return Gtk.ScrolledWindow.do_size_allocate(self, alloc)


class Notebook(Gtk.Notebook):
    """A regular gtk.Notebook, except when appending a page, if no
    label is given, the page's 'title' attribute (either a string or
    a widget) is used."""

    def __init__(self, *args, **kwargs):
        super(Notebook, self).__init__(*args, **kwargs)
        self.connect("key-press-event", self.__key_pressed)

    def __key_pressed(self, widget, event):
        # alt+X switches to page X
        for i in xrange(self.get_n_pages()):
            if is_accel(event, "<alt>%d" % (i + 1)):
                self.set_current_page(i)
                return True
        return False

    def do_size_allocate(self, alloc):
        ctx = self.get_style_context()
        border = ctx.get_border(ctx.get_state())

        toplevel = self.get_toplevel()
        # try to get the child so we ignore the CSD
        toplevel = toplevel.get_child() or toplevel

        try:
            dx, dy = self.translate_coordinates(toplevel, 0, 0)
        except TypeError:
            GLib.idle_add(self.queue_resize)
            return Gtk.Notebook.do_size_allocate(self, alloc)

        dx = max(0, dx)
        dy = max(0, dy)

        # all 0 since gtk+ 3.12..
        border.left = border.top = border.right = border.bottom = 1

        top_alloc = toplevel.get_allocation()
        width, height = top_alloc.width, top_alloc.height
        if alloc.height + dy == height:
            alloc.height += border.bottom

        if alloc.width + dx == width:
            alloc.width += border.right

        if dy == 0:
            alloc.y -= border.top
            alloc.height += border.top

        if dx == 0:
            alloc.x -= border.left
            alloc.width += border.left

        return Gtk.Notebook.do_size_allocate(self, alloc)

    def append_page(self, page, label=None):
        if label is None:
            try:
                label = page.title
            except AttributeError:
                raise TypeError("no page.title and no label given")

        if not isinstance(label, Gtk.Widget):
            label = Gtk.Label(label=label)
        super(Notebook, self).append_page(page, label)


def Frame(label, child=None):
    """A Gtk.Frame with no shadow, 12px left padding, and 6px top padding."""
    frame = Gtk.Frame()
    label_w = Gtk.Label()
    label_w.set_markup("<b>%s</b>" % util.escape(label))
    align = Align(left=12, top=6)
    frame.add(align)
    frame.set_shadow_type(Gtk.ShadowType.NONE)
    frame.set_label_widget(label_w)
    if child:
        align.add(child)
        label_w.set_mnemonic_widget(child)
        label_w.set_use_underline(True)
    return frame


class Align(Gtk.Alignment):
    """Note: With gtk3.12+ we could replace this with a Gtk.Bin +
    margin properties.
    """

    def __init__(self, child=None,
                 top=0, right=0, bottom=0, left=0, border=0,
                 halign=Gtk.Align.FILL, valign=Gtk.Align.FILL):

        def align_to_xy(a):
            """(xyalign, xyscale)"""

            if a == Gtk.Align.FILL:
                return 0.0, 1.0
            elif a == Gtk.Align.START:
                return 0.0, 0.0
            elif a == Gtk.Align.END:
                return 1.0, 0.0
            elif a == Gtk.Align.CENTER:
                return 0.5, 0.0
            else:
                return 0.5, 1.0

        xalign, xscale = align_to_xy(halign)
        yalign, yscale = align_to_xy(valign)
        bottom_padding = border + bottom
        top_padding = border + top
        left_padding = border + left
        right_padding = border + right

        super(Align, self).__init__(xalign=xalign, xscale=xscale,
            yalign=yalign, yscale=yscale, bottom_padding=bottom_padding,
            top_padding=top_padding, left_padding=left_padding,
            right_padding=right_padding)

        if child is not None:
            self.add(child)

    def get_margin_top(self):
        return self.props.top_padding

    def get_margin_bottom(self):
        return self.props.bottom_padding

    def get_margin_left(self):
        return self.props.left_padding

    def get_margin_right(self):
        return self.props.right_padding


def MenuItem(label, icon_name=None):
    """An ImageMenuItem with a custom label and stock image."""

    if icon_name is None:
        return Gtk.MenuItem.new_with_mnemonic(label)

    item = Gtk.ImageMenuItem.new_with_mnemonic(label)
    item.set_always_show_image(True)
    image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
    image.show()
    item.set_image(image)
    return item


def _Button(type_, label, icon_name, size):
    if icon_name is None:
        return Gtk.Button.new_with_mnemonic(label)

    align = Align(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
    hbox = Gtk.HBox(spacing=2)
    image = Gtk.Image.new_from_icon_name(icon_name, size)
    hbox.pack_start(image, True, True, 0)
    label = Gtk.Label(label=label)
    label.set_use_underline(True)
    hbox.pack_start(label, True, True, 0)
    align.add(hbox)
    align.show_all()
    button = type_()
    button.add(align)
    return button


def Button(label, icon_name=None, size=Gtk.IconSize.BUTTON):
    """A Button with a custom label and stock image. It should pack
    exactly like a stock button.
    """

    return _Button(Gtk.Button, label, icon_name, size)


def ToggleButton(label, icon_name=None, size=Gtk.IconSize.BUTTON):
    """A ToggleButton with a custom label and stock image. It should pack
    exactly like a stock button.
    """

    return _Button(Gtk.ToggleButton, label, icon_name, size)


class Paned(Gtk.Paned):

    def __init__(self, *args, **kwargs):
        super(Paned, self).__init__(*args, **kwargs)
        self.ensure_wide_handle()

    def ensure_wide_handle(self):
        if gtk_version >= (3, 19):
            self.props.wide_handle = True
            add_css(self, """
                paned separator {
                    border-width: 0;
                    background-image: none;
                }
            """)
            return

        if hasattr(self.props, "wide_handle"):
            # gtk 3.16
            self.props.wide_handle = True
            add_css(self, """
                GtkPaned {
                    border-width: 0;
                }
            """)
            return

        # gtk 3.14
        add_css(self, """
            GtkPaned {
                -GtkPaned-handle-size: 6;
                background-image: none;
                margin: 0;
                border-width: 0;
            }
        """)


class RPaned(Paned):
    """A Paned that supports relative (percentage) width/height setting."""

    ORIENTATION = None

    def __init__(self, *args, **kwargs):
        if self.ORIENTATION is not None:
            kwargs["orientation"] = self.ORIENTATION
        super(RPaned, self).__init__(*args, **kwargs)
        # before first alloc: save value in relative and set on the first alloc
        # after the first alloc: use the normal properties
        self.__alloced = False
        self.__relative = None

    def set_relative(self, v):
        """Set the relative position of the separator, [0..1]."""

        if self.__alloced:
            max_pos = self.get_property('max-position')
            if not max_pos:
                # no children
                self.__relative = v
                return
            self.set_position(int(v * max_pos))
        else:
            self.__relative = v

    def get_relative(self):
        """Return the relative position of the separator, [0..1]."""

        if self.__alloced:
            max_pos = self.get_property('max-position')
            if not max_pos:
                # no children
                return self.__relative
            return (float(self.get_position()) / max_pos)
        elif self.__relative is not None:
            return self.__relative
        else:
            # before first alloc and set_relative not called
            return 0.5

    def do_size_allocate(self, *args):
        ret = Gtk.HPaned.do_size_allocate(self, *args)
        if not self.__alloced and self.__relative is not None:
            self.__alloced = True
            self.set_relative(self.__relative)
            # call again so the children get alloced
            ret = Gtk.HPaned.do_size_allocate(self, *args)
        self.__alloced = True
        return ret


class RHPaned(RPaned):
    ORIENTATION = Gtk.Orientation.HORIZONTAL


class RVPaned(RPaned):
    ORIENTATION = Gtk.Orientation.VERTICAL


class ConfigRPaned(RPaned):
    def __init__(self, section, option, default, *args, **kwargs):
        super(ConfigRPaned, self).__init__(*args, **kwargs)
        self.set_relative(config.getfloat(section, option, default))
        self.connect('notify::position', self.__changed, section, option)

    def __changed(self, widget, event, section, option):
        if self.get_property('position-set'):
            config.set(section, option, str(self.get_relative()))


class ConfigRHPaned(ConfigRPaned):
    ORIENTATION = Gtk.Orientation.HORIZONTAL


class ConfigRVPaned(ConfigRPaned):
    ORIENTATION = Gtk.Orientation.VERTICAL


class _SmallImageButton(object):
    """A button for images with less padding"""

    def __init__(self, **kwargs):
        super(_SmallImageButton, self).__init__(**kwargs)

        self.set_size_request(26, 26)
        add_css(self, """
            * {
                padding: 0px;
            }
        """)


class SmallImageButton(_SmallImageButton, Gtk.Button):
    pass


class SmallImageToggleButton(_SmallImageButton, Gtk.ToggleButton):
    pass


def EntryCompletion(words):
    """Simple string completion."""
    model = Gtk.ListStore(str)
    for word in sorted(words):
        model.append(row=[word])
    comp = Gtk.EntryCompletion()
    comp.set_model(model)
    comp.set_text_column(0)
    return comp


def RadioMenuItem(*args, **kwargs):
    """RadioMenuItem that allows None for group"""

    if kwargs.get("group", None) is None:
        kwargs.pop("group", None)
    return Gtk.RadioMenuItem(*args, **kwargs)


def SeparatorMenuItem(*args, **kwargs):
    # https://bugzilla.gnome.org/show_bug.cgi?id=670575
    # PyGObject 3.2 always sets a label in __init__
    if not args and not kwargs:
        return Gtk.SeparatorMenuItem.new()
    return Gtk.SeparatorMenuItem(*args, **kwargs)


def SymbolicIconImage(name, size, fallbacks=None):
    """Gtk.Image that displays a symbolic version of 'name' and falls
    back to the non-symbolic one.
    """

    symbolic_name = name + "-symbolic"
    gicon = Gio.ThemedIcon.new_from_names([symbolic_name, name])
    return Gtk.Image.new_from_gicon(gicon, size)


class CellRendererPixbuf(Gtk.CellRendererPixbuf):

    def __init__(self, *args, **kwargs):
        super(CellRendererPixbuf, self).__init__(*args, **kwargs)
        if gtk_version < (3, 16):
            # was deprecated in 3.16 and defaults to True now. Since it was
            # False before force it here so we have the same behavior in all
            # cases
            self.set_property("follow-state", True)


class Action(Gtk.Action):
    def __init__(self, *args, **kargs):
        # Older pygobject didn't pass through kwargs to GObject.Object
        # so skip the override __init__
        GObject.Object.__init__(self, *args, **kargs)


class ToggleAction(Gtk.ToggleAction):
    def __init__(self, *args, **kargs):
        GObject.Object.__init__(self, *args, **kargs)


class RadioAction(Gtk.RadioAction):
    def __init__(self, *args, **kargs):
        GObject.Object.__init__(self, *args, **kargs)
