"""
This plugin provides a debugging command-line interface to qplan.

**Usage**

Get a list of commands and parameters::

        g> help

Execute a shell command::

        g> !cmd arg arg ...

**Notes**

An especially powerful tool is to use the ``reload_global`` command to
reload a plugin when you are developing that plugin.  This avoids having to
restart qplan and laboriously reload data, etc.  Simply close the plugin,
execute "reload_global" command (see the help!) and then start the plugin
again.

.. note:: If you have modifed modules *other* than the plugin itself,
          these will not be reloaded by these commands.

"""
import time
import os

from ginga.gw import Widgets
from qplan.plugins import PlBase
from ginga.util import grc

__all__ = ['Command']


class Command(PlBase.Plugin):

    def __init__(self, controller):
        # superclass defines some variables for us, like logger
        super(Command, self).__init__(controller)

        self.cmd_w = None
        self.hist_w = None
        self.histlimit = 5000

        self._cmdobj = CommandInterpreter(controller, self)

    def build_gui(self, container):

        vbox = Widgets.VBox()

        self.msg_font = self.fv.get_font('fixed', 12)

        vbox.add_widget(Widgets.Label("Output:"))
        tw = Widgets.TextArea(wrap=True, editable=False)
        tw.set_font(self.msg_font)
        tw.set_limit(self.histlimit)
        self.hist_w = tw

        vbox2 = Widgets.VBox()
        vbox2.add_widget(tw, stretch=1)
        vbox2.add_widget(Widgets.Label(''), stretch=0)

        vbox.add_widget(vbox2, stretch=1)

        vbox2 = Widgets.VBox()
        vbox2.add_widget(Widgets.Label("Type command here:"))
        self.cmd_w = Widgets.TextEntry()
        self.cmd_w.set_font(self.msg_font)
        vbox2.add_widget(self.cmd_w, stretch=0)
        self.cmd_w.add_callback('activated', self.exec_cmd_cb)
        vbox.add_widget(vbox2, stretch=0)

        btns = Widgets.HBox()
        btns.set_spacing(4)
        btns.set_border_width(4)

        btn = Widgets.Button("Close")
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn)
        btn = Widgets.Button("Help")
        btn.add_callback('activated', lambda w: self.help())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)
        vbox.add_widget(btns, stretch=0)

        container.add_widget(vbox, stretch=1)

    def exec_cmd(self, text):
        text = text.strip()
        self.log("g> " + text, w_time=True)

        if text.startswith('!'):
            # escape to shell for this command
            self.exec_shell(text[1:])
            return

        args = text.split()
        cmd, tokens = args[0], args[1:]

        # process args
        args, kwargs = grc.prep_args(tokens)

        try:
            method = getattr(self._cmdobj, "cmd_" + cmd.lower())

        except AttributeError:
            self.log("|E| No such command: '%s'" % (cmd))
            return

        try:
            res = method(*args, **kwargs)
            if res is not None:
                self.log(str(res))

            # this brings the focus back to the command bar if the command
            # causes a new window to be opened
            self.cmd_w.focus()

        except Exception as e:
            self.log("|E| Error executing '%s': %s" % (text, str(e)))
            # TODO: add traceback

    def exec_cmd_cb(self, w):
        text = w.get_text()
        self.exec_cmd(text)
        w.set_text("")

    def exec_shell(self, cmd_str):
        res, out, err = grc.get_exitcode_stdout_stderr(cmd_str)
        if len(out) > 0:
            self.log(out.decode('utf-8'))
        if len(err) > 0:
            self.log(err.decode('utf-8'))
        if res != 0:
            self.log("command terminated with error code %d" % res)

    def log(self, text, w_time=False):
        if self.hist_w is not None:
            pfx = ''
            if w_time:
                pfx = time.strftime("%H:%M:%S", time.localtime()) + ": "
            self.controller.gui_do(self.hist_w.append_text, pfx + text + '\n',
                                   autoscroll=True)
            #self.controller.update_pending()

    def close(self):
        self.controller.stop_plugin(str(self))
        return True

    def __str__(self):
        return 'command'


class CommandInterpreter(object):

    def __init__(self, controller, plugin):
        super(CommandInterpreter, self).__init__()

        self.controller = controller
        self.plugin = plugin
        self.logger = plugin.logger
        self.log = plugin.log

    ##### COMMANDS #####

    def cmd_help(self, *args):
        """help [cmd]

        Get general help, or help for command `cmd`.
        """
        if len(args) > 0:
            cmdname = args[0].lower()
            try:
                method = getattr(self, "cmd_" + cmdname)
                doc = method.__doc__
                if doc is None:
                    self.log("Sorry, no documentation found for '%s'" % (
                        cmdname))
                else:
                    self.log("%s: %s" % (cmdname, doc))
            except AttributeError:
                self.log("No such command '%s'; type help for general help." % (
                    cmdname))
        else:
            res = []
            for attrname in dir(self):
                if attrname.startswith('cmd_'):
                    method = getattr(self, attrname)
                    doc = method.__doc__
                    cmdname = attrname[4:]
                    if doc is None:
                        doc = "no documentation"
                    res.append("%s: %s" % (cmdname, doc))
            self.log('\n'.join(res))

    def cmd_reload_global(self, plname):
        """reload_global `plname`

        Reload the *global* plugin named `plname`.  You should close
        all instances of the plugin before attempting to reload.
        """
        gpmon = self.controller.gpmon
        p_info = gpmon.get_plugin_info(plname)
        gpmon.stop_plugin(p_info)
        #self.controller.update_pending(0.5)
        self.controller.mm.load_module(plname)
        gpmon.reload_plugin(plname)
        self.controller.start_plugin(plname)
        return True

    def cmd_reload_module(self, modname):
        """reload_module `modname`

        Reload the Python module named `modname`.
        """
        self.controller.mm.load_module(modname)
        return True

    def cmd_cd(self, *args):
        """cd [path]

        Change the current working directory to `path`.
        """
        if len(args) == 0:
            path = os.environ['HOME']
        else:
            path = args[0]
        os.chdir(path)
        self.cmd_pwd()

    def cmd_ls(self, *args):
        """ls [options]

        Execute list files command
        """
        cmd_str = ' '.join(['ls'] + list(args))
        self.plugin.exec_shell(cmd_str)

    def cmd_pwd(self):
        """pwd

        List the current working directory.
        """
        self.log("%s" % (os.getcwd()))
