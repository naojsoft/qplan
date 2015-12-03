#
# Logger.py -- Logging plugin
#
# Eric Jeschke (eric@naoj.org)
#
import logging

from ginga.gw import Widgets
import PlBase

class Logger(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(Logger, self).__init__(model, view, controller, logger)

        self.histlimit = 1000
        self.histmax = 10000
        self.levels = (('Error', logging.ERROR),
                       ('Warn',  logging.WARN),
                       ('Info',  logging.INFO),
                       ('Debug', logging.DEBUG))
        self.autoscroll = True
        self.tw = None


    def build_gui(self, container):

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)

        tw = Widgets.TextArea(editable=False, wrap=False)
        font = self.view.get_font("Courier", 10)
        tw.set_font(font)
        self.tw = tw

        container.add_widget(self.tw, stretch=1)

    def set_history(self, histlimit):
        assert histlimit <= self.histmax, \
               Exception("Limit exceeds maximum value of %d" % (self.histmax))
        self.histlimit = histlimit
        self.logger.debug("Logging history limit set to %d" % (
            histlimit))
        self.tw.set_limit(histlimit)

    def set_history_cb(self, w, val):
        self.set_history(val)

    def set_loglevel_cb(self, w, index):
        name, level = self.levels[index]
        self.fv.set_loglevel(level)
        self.logger.info("GUI log level changed to '%s'" % (
            name))

    def set_autoscroll_cb(self, w, val):
        self.autoscroll = val

    def log(self, text):
        if self.tw != None:
            self.tw.append_text(text, autoscroll=self.autoscroll)

    def clear(self):
        self.tw.clear()
        return True


#END
