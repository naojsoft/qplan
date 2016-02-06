#
# Execute.py -- Execute plugin
#
# Eric Jeschke (eric@naoj.org)
#
import os
import StringIO

from ginga.misc import Widgets
from ginga.qtw import QtHelp

# Gen2
import remoteObjects as ro

import Report
#import FOCAS
import HSC

class Execute(Report.Report):

    def __init__(self, model, view, controller, logger):
        super(Execute, self).__init__(model, view, controller, logger)

        self.svcname = 'integgui0'
        self.ig = None
        self.refresh_ig()
        self.debug_mode = False
        #self.debug_mode = True

    def build_gui(self, container):
        super(Execute, self).build_gui(container)

        captions = (('Send', 'button', 'Resolve', 'button',
                     'Refresh', 'button'),
                    )
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w = b

        b.send.add_callback('activated', self.send_cb)
        b.resolve.add_callback('activated', self.resolve_cb)
        b.refresh.add_callback('activated', self.refresh_cb)

        self.vbox.add_widget(w, stretch=0)

    def refresh_ig(self):
        if self.ig is None:
            ro.init()
        self.ig = ro.remoteObjectProxy(self.svcname)

    def _get_targets(self, oblist):
        targets = set([])
        for ob in oblist:
            targets.add(ob.target)
        return targets

    def send_cb(self, w):

        oblist = self._get_selected_obs()
        targets = self._get_targets(oblist)

        try:
            #converter = FOCAS.Converter(self.logger)
            converter = HSC.Converter(self.logger)

            # buffer for OPE output
            out_f = StringIO.StringIO()

            # write preamble
            converter.write_ope_header(out_f, targets)

            # convert each OB
            for ob in oblist:
                converter.ob_to_ope(ob, out_f)

            # here's the OPE file
            ope_buf = out_f.getvalue()
            self.logger.debug("Conversion produced:\n" + ope_buf)

            # write buffer to a file
            filepath = os.path.join(os.environ['HOME'], 'Procedure', 'OCS',
                                    'Queue.ope')
            with open(filepath, 'w') as out_f:
                out_f.write(ope_buf)

            self.logger.debug("Ope result:\n" + ope_buf + "\n")
            if not self.debug_mode:
                # tell integgui2 to reload this file
                self.ig.load_page(filepath)

        except Exception as e:
            self.logger.error("Error sending OBs: %s" % (str(e)))

        return True


    def resolve_cb(self, w):
        oblist = self._get_selected_obs()

        try:
            pInfo = self.view.get_plugin('resolution')
            pInfo.obj.resolve_obs(oblist)

        except Exception as e:
            self.logger.error("Error resolving OBs: %s" % (str(e)))

        return True


    def refresh_cb(self, w):
        try:
            self.add_schedule(self.cur_schedule)
            info = self.schedules[self.cur_schedule]

            if self.gui_up:
                self.view.gui_do(self.set_text, info.report)

        except KeyError:
            pass



#END
