#
# Logger.py -- Logging plugin
#
# Eric Jeschke (eric@naoj.org)
#
import logging

from ginga.gw import Widgets
from ginga.misc import Bunch

from qplan.plugins import PlBase

class Logger(PlBase.Plugin):

    def __init__(self, controller):
        super(Logger, self).__init__(controller)

        self.histlimit = 10000
        self.histmax = 100000
        self.levels = (('Error', logging.ERROR),
                       ('Warn',  logging.WARN),
                       ('Info',  logging.INFO),
                       ('Debug', logging.DEBUG))
        self.autoscroll = True
        self.tw = None
        self.w = Bunch.Bunch(caseless=True)
        self._save_buf = []


    def build_gui(self, container):
        vbox = Widgets.VBox()

        vbox.set_margins(2, 2, 2, 2)
        vbox.set_spacing(4)

        tw = Widgets.TextArea(editable=False, wrap=False)
        self.font = self.view.get_font('Courier', 12)
        tw.set_limit(self.histlimit)
        tw.set_font(self.font)
        self.tw = tw
        tw.set_text('\n'.join(self._save_buf))
        self._save_buf = []

        sw = Widgets.ScrollArea()
        sw.set_widget(self.tw)

        vbox.add_widget(sw, stretch=1)

        captions = [('Level', 'combobox', 'History', 'spinbutton',
                     'Auto scroll', 'checkbutton', 'Clear', 'button'),
                    ]
        w, b = Widgets.build_info(captions)
        self.w.update(b)

        combobox = b.level
        for (name, level) in self.levels:
            combobox.append_text(name)
        combobox.set_index(1)
        combobox.add_callback('activated', self.set_loglevel_cb)
        combobox.set_tooltip("Set the logging level")

        spinbox = b.history
        spinbox.set_limits(100, self.histmax, incr_value=10)
        spinbox.set_value(self.histlimit)
        spinbox.add_callback('value-changed', self.set_history_cb)
        spinbox.set_tooltip("Set the logging history line limit")

        btn = b.auto_scroll
        btn.set_state(self.autoscroll)
        btn.set_tooltip("Scroll the log window automatically")
        btn.add_callback('activated', self.set_autoscroll_cb)

        btn = b.clear
        btn.add_callback('activated', lambda w: self.clear())
        btn.set_tooltip("Clear the log history")
        vbox.add_widget(w, stretch=0)

        btns = Widgets.HBox()
        btns.set_border_width(4)
        btns.set_spacing(4)

        btn = Widgets.Button("Close")
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn)
        btn = Widgets.Button("Help")
        btn.add_callback('activated', lambda w: self.help())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)
        vbox.add_widget(btns, stretch=0)

        container.add_widget(vbox, stretch=1)


    def set_history(self, histlimit):
        if histlimit > self.histmax:
            raise Exception(
                "Limit exceeds maximum value of %d" % (self.histmax))
        self.histlimit = histlimit
        self.logger.debug("Logging history limit set to %d" % (
            histlimit))
        self.tw.set_limit(histlimit)

    def set_history_cb(self, w, val):
        self.set_history(val)

    def set_loglevel_cb(self, w, index):
        name, level = self.levels[index]
        self.controller.set_loglevel(level)
        self.logger.info("GUI log level changed to '%s'" % (
            name))

    def set_autoscroll_cb(self, w, val):
        self.autoscroll = val

    def log(self, text):
        if self.tw is not None:
            self.tw.append_text(text, autoscroll=self.autoscroll)
        else:
            self._save_buf.append(text)
            self._save_buf = self._save_buf[-self.histlimit:]

    def clear(self):
        self.tw.clear()
        self.tw.set_font(self.font)
        return True

    def stop(self):
        self.tw = None

    def close(self):
        self.controller.stop_plugin(str(self))
        return True

    def __str__(self):
        return 'logger'

#END
