#
# Execute.py -- Execute plugin
# 
# Eric Jeschke (eric@naoj.org)
#
import StringIO

from ginga.misc import Widgets
from ginga.qtw import QtHelp

# Gen2
import remoteObjects as ro

import Report
import SPCAM

class Execute(Report.Report):

    def __init__(self, model, view, controller, logger):
        super(Execute, self).__init__(model, view, controller, logger)

        self.svcname = 'integgui0'
        self.ig = None
        self.refresh_ig()

    def build_gui(self, container):
        super(Execute, self).build_gui(container)

        captions = (('Send', 'button', 'Resolve', 'button'),
                    )
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w = b

        b.send.add_callback('activated', self.send_cb)
        b.resolve.add_callback('activated', self.resolve_cb)

        self.vbox.add_widget(w, stretch=0)

    def refresh_ig(self):
        if self.ig is None:
            ro.init()
        self.ig = ro.remoteObjectProxy(self.svcname)
            
    def send_cb(self, w):

        oblist = self._get_selected_obs()

        try:
            converter = SPCAM.Converter(self.logger)

            # buffer for OPE output
            out_f = StringIO.StringIO()

            # write preamble
            converter.write_ope_header(out_f)

            # convert each OB
            for ob in oblist:
                converter.ob_to_ope(ob, out_f)

            # here's the OPE file
            ope_buf = out_f.getvalue()

            # send to integgui2
            self.ig.queue_load_ope(ope_buf)

        except Exception as e:
            self.logger.error("Error sending OBs: %s" % (str(e)))

        return True


    def resolve_cb(self, w):
        oblist = self._get_selected_obs()

        try:
            obj = self.view.get_plugin('Resolution')
            obj.resolve_obs(oblist)

        except Exception as e:
            self.logger.error("Error resolving OBs: %s" % (str(e)))

        return True

#END
