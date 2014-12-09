# stdlib imports
import sys, os
import platform
import traceback

from ginga.qtw import QtHelp, QtMain
from ginga.qtw.QtHelp import QtGui, QtCore, QFont, MenuBar
from ginga.misc import Bunch

moduleHome = os.path.split(sys.modules[__name__].__file__)[0]
icon_path = os.path.abspath(os.path.join(moduleHome, '..', 'icons'))
rc_file = os.path.join(moduleHome, "qt_rc")

# Local application imports
import qsim


class ViewError(Exception):
    pass

class Viewer(QtMain.QtMain):

    def __init__(self, logger, ev_quit):
       # call superclass constructors--sets self.app
        QtMain.QtMain.__init__(self, logger=logger, ev_quit=ev_quit)
        if os.path.exists(rc_file):
            self.app.setStyleSheet(rc_file)

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
        QtGui.QToolTip.setFont(self.font11)

        self.ds = QtHelp.Desktop()
        self.ds.make_desktop(layout, widgetDict=self.w)

        for root in self.ds.toplevels:
            # add delete/destroy callbacks
            root.setWindowTitle("Queue Planner")
        self.ds.add_callback('all-closed', self.quit)
        
        self.w.root = root

        menuholder = self.w['menu']
        self.w.menubar = self.add_menus(menuholder)

        statusholder = self.w['status']
        self.add_statusbar(statusholder)

        self.w.root.show()


    def add_menus(self, holder):
        menubar = MenuBar()

        # NOTE: Special hack for Mac OS X, otherwise the menus
        # do not get added to the global OS X menu
        macos_ver = platform.mac_ver()[0]
        if len(macos_ver) > 0:
            self.w['top'].layout().addWidget(menubar, stretch=0)
        else:
            holder.layout().addWidget(menubar, stretch=1)

        # create a File pulldown menu, and add it to the menu bar
        filemenu = menubar.add_name("File")

        sep = menubar.make_action('')
        sep.setSeparator(True)
        filemenu.addAction(sep)
        
        item = menubar.make_action("Quit")
        item.triggered.connect(self.quit)
        filemenu.addAction(item)

        # create a Option pulldown menu, and add it to the menu bar
        ## optionmenu = menubar.add_name("Option")

    def add_statusbar(self, holder):
        self.w.status = QtGui.QStatusBar()
        holder.layout().addWidget(self.w.status, stretch=1)
   
    def windowClose(self, *args):
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
            w.deleteLater()

    def stop(self):
        self.ev_quit.set()

    def get_font(self, font_type, point_size):
        font_family = self.settings.get(font_type, 'sans')
        font = QFont(font_family, point_size)
        return font

    def set_pos(self, x, y):
        self.w.root.move(x, y)

    def set_size(self, wd, ht):
        self.w.root.resize(wd, ht)

    def set_geometry(self, geometry):
        # Painful translation of X window geometry specification
        # into correct calls to Qt
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
            dim = map(int, dim.split('x'))
            self.set_size(*dim)

        if len(coords) > 0:
            # user specified position
            coords = map(int, coords)
            self.set_pos(*coords)

    def load_plugin(self, pluginName, moduleName, className, wsName, tabName):

        widget = QtGui.QWidget()

        # Record plugin info
        canonicalName = pluginName.lower()
        bnch = Bunch.Bunch(caseless=True,
                           name=canonicalName, officialname=pluginName,
                           modulename=moduleName, classname=className,
                           wsname=wsName, tabname=tabName, widget=widget)
        
        self.plugins[pluginName] = bnch
        
        try:
            module = self.mm.loadModule(moduleName)

            # Look up the module and class
            module = self.mm.getModule(moduleName)
            klass = getattr(module, className)

            # instantiate the class
            pluginObj = klass(self.model, self, self.controller,
                              self.logger)
            # Save a reference to the plugin object so we can use it
            # later
            self.plugins[pluginName].setvals(obj=pluginObj)

            # Build the plugin GUI
            pluginObj.build_gui(widget)

            # Add the widget to a workspace and save the tab name in
            # case we need to delete the widget later on.
            dsTabName = self.ds.add_tab(wsName, widget, 2, tabName)
            self.plugins[pluginName].setvals(wsTabName=dsTabName)

            # Start the plugin
            pluginObj.start()

        except Exception, e:
            errstr = "Plugin '%s' failed to initialize: %s" % (
                className, str(e))
            self.logger.error(errstr)
            try:
                (type, value, tb) = sys.exc_info()
                tb_str = "\n".join(traceback.format_tb(tb))
                self.logger.error("Traceback:\n%s" % (tb_str))
                
            except Exception, e:
                tb_str = "Traceback information unavailable."
                self.logger.error(tb_str)
                
            vbox = QtGui.QVBoxLayout()
            vbox.setContentsMargins(4, 4, 4, 4)
            vbox.setSpacing(0)
            widget.setLayout(vbox)
            
            textw = QtGui.QTextEdit()
            textw.append(str(e) + '\n')
            textw.append(tb_str)
            textw.setReadOnly(True)
            vbox.addWidget(textw, stretch=1)
                
            self.ds.add_tab(wsName, widget, 2, tabName)

    def close_plugin(self, pluginName):
        bnch = self.plugins[pluginName]
        self.logger.info('calling stop() for plugin %s' % (pluginName))
        bnch.obj.stop()
        self.logger.info('calling remove_tab() for plugin %s' % (pluginName))
        self.ds.remove_tab(bnch.wsTabName)
        return True
     
    def close_all_plugins(self):
        for pluginName in self.plugins:
            try:
                self.close_plugin(pluginName)
            except Exception as e:
                self.logger.error('Exception while calling stop for plugin %s: %s' % (pluginName, e))
        return True
    
    def reload_plugin(self, pluginName):
        pInfo = self.plugins[pluginName]
        try:
            self.close_plugin(pluginName)
        except:
            pass
        
        return self.load_plugin(pInfo.officialname, pInfo.modulename,
                                pInfo.classname, pInfo.wsname,
                                pInfo.tabname)

    def logit(self, text):
        try:
            pInfo = self.plugins['logger']
            self.gui_do(pInfo.obj.log, text)
        except:
            pass
        

#END
