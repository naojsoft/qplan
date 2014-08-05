#
# Logger.py -- Logging plugin
# 
# Eric Jeschke (eric@naoj.org)
#
import logging

from PyQt4 import QtGui, QtCore
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

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        container.setLayout(layout)

        tw = QtGui.QTextEdit()
        tw.setReadOnly(True)
        tw.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        font = QtGui.QFont("Courier", 10)
        tw.setFont(font)
        self.tw = tw
        
        layout.addWidget(self.tw, stretch=1)

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
            self.tw.append(text)
            if self.autoscroll:
                self.tw.moveCursor(QtGui.QTextCursor.End)
                self.tw.moveCursor(QtGui.QTextCursor.StartOfLine)
                self.tw.ensureCursorVisible()

    def clear(self):
        self.tw.clear()
        return True


#END
