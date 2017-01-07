#
# This is open-source software licensed under a BSD license.
# Please see the file LICENSE.txt for details.
#
# stdlib imports
import sys, os
import platform
import traceback

from ginga.gw import GwHelp, GwMain, Widgets, Desktop
from ginga.gw.PluginManager import PluginManager
from ginga.misc import Bunch
from six.moves import map
from six.moves import zip

moduleHome = os.path.split(sys.modules[__name__].__file__)[0]
icon_path = os.path.abspath(os.path.join(moduleHome, '..', 'icons'))
rc_file = os.path.join(moduleHome, "qt_rc")

# Local application imports
from . import qsim


class ViewError(Exception):
    pass

class Viewer(GwMain.GwMain, Widgets.Application):

    def __init__(self, logger, ev_quit):
        Widgets.Application.__init__(self, logger=logger)
        GwMain.GwMain.__init__(self, logger=logger, ev_quit=ev_quit,
                               app=self)
        self.w = Bunch.Bunch()

        # For now...
        self.controller = self

        # dictionary of plugins
        self.plugins = {}

    def build_toplevel(self, layout):
        self.font = self.get_font('fixedFont', 12)
        self.font11 = self.get_font('fixedFont', 11)
        self.font14 = self.get_font('fixedFont', 14)
        self.font18 = self.get_font('fixedFont', 18)

        self.w.tooltips = None

        self.ds = Desktop.Desktop(self)
        self.ds.make_desktop(layout, widget_dict=self.w)

        self.gpmon = PluginManager(self.logger, self, self.ds, self.mm)

        for win in self.ds.toplevels:
            # add delete/destroy callbacks
            win.add_callback('close', self.quit)
            win.set_title("Queue Planner")
            root = win
        self.ds.add_callback('all-closed', self.quit)

        self.w.root = root

        menuholder = self.w['menu']
        self.w.menubar = self.add_menus(menuholder)

        statusholder = self.w['status']
        self.add_statusbar(statusholder)

        self.w.root.show()


    def add_menus(self, holder):
        menubar = Widgets.Menubar()
        self.menubar = menubar

        holder.add_widget(menubar, stretch=1)

        # create a File pulldown menu, and add it to the menu bar
        filemenu = menubar.add_name("File")
        filemenu.add_separator()

        item = filemenu.add_name("Quit")
        item.add_callback('activated', lambda w: self.quit())

        # create a Option pulldown menu, and add it to the menu bar
        ## optionmenu = menubar.add_name("Option")

    def add_statusbar(self, holder):
        self.w.status = Widgets.StatusBar()
        holder.add_widget(self.w.status, stretch=1)

    def window_close(self, *args):
        """Quit the application.
        """
        self.quit()

    def quit(self, *args):
        """Quit the application.
        """
        self.logger.info("Attempting to shut down the application...")
        self.stop()

        root = self.w.root
        self.w.root = None
        while len(self.ds.toplevels) > 0:
            w = self.ds.toplevels.pop()
            w.delete()

    def stop(self):
        self.ev_quit.set()

    def get_font(self, font_family, point_size):
        #font_family = self.settings.get(font_type, 'sans')
        font = GwHelp.get_font(font_family, point_size)
        return font

    def set_pos(self, x, y):
        self.w.root.move(x, y)

    def set_size(self, wd, ht):
        self.w.root.resize(wd, ht)

    def set_geometry(self, geometry):
        # Painful translation of X window geometry specification
        # into correct calls to widget
        coords = geometry.replace('+', ' +')
        coords = coords.replace('-', ' -')
        coords = coords.split()
        if 'x' in coords[0]:
            # spec includes dimensions
            dim = coords[0]
            coords = coords[1:]
        else:
            # spec is position only
            dim = None

        if dim != None:
            # user specified dimensions
            dim = list(map(int, dim.split('x')))
            self.set_size(*dim)

        if len(coords) > 0:
            # user specified position
            coords = list(map(int, coords))
            self.set_pos(*coords)

    def load_plugin(self, name, spec):

        self.mm.load_module(spec.module, pfx=None)

        self.gpmon.load_plugin(name, spec)

        start = spec.get('start', True)
        if start:
            self.start_plugin(name, raise_tab=False)

    def start_plugin(self, plugin_name, raise_tab=False):
        self.gpmon.start_plugin_future(None, plugin_name, None)
        if raise_tab:
            p_info = self.gpmon.get_plugin_info(plugin_name)
            self.ds.raise_tab(p_info.tabname)

    def close_plugin(self, plugin_name):
        self.logger.info('deactivating plugin %s' % (plugin_name))
        self.gpmon.deactivate(plugin_name)
        return True

    def close_all_plugins(self):
        self.gpmon.stop_all_plugins()
        return True

    def reload_plugin(self, plugin_name):
        self.gpmon.reload_plugin(plugin_name)

    def get_plugin_info(self, plugin_name):
        return self.gpmon.get_plugin_info(plugin_name)

    def get_plugin(self, plugin_name):
        return self.gpmon.get_plugin(plugin_name)

    def logit(self, text):
        try:
            obj = self.get_plugin('logger')
            self.gui_do(obj.log, text)
        except:
            pass

    def show_error(self, errmsg, raisetab=True):
        obj = self.get_plugin('Errors')
        obj.add_error(errmsg)
        if raisetab:
            self.ds.raise_tab('Errors')

    def error_wrap(self, method, *args, **kwargs):
        try:
            return method(*args, **kwargs)

        except Exception as e:
            errmsg = "\n".join([e.__class__.__name__, str(e)])
            try:
                (type, value, tb) = sys.exc_info()
                tb_str = "\n".join(traceback.format_tb(tb))
            except Exception as e:
                tb_str = "Traceback information unavailable."
            errmsg += tb_str
            self.logger.error(errmsg)
            self.gui_do(self.show_error, errmsg, raisetab=True)


#END
