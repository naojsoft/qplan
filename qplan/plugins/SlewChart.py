#
# SlewChart.py -- Slew chart plugin
#
# E. Jeschke
#
import numpy as np
from datetime import datetime

from ginga.misc import Bunch
from ginga.gw import Widgets, Viewers

from qplan.plugins import PlBase
from qplan import common


class SlewChart(PlBase.Plugin):

    def __init__(self, controller):
        super(SlewChart, self).__init__(controller)

        self.schedules = {}
        self.initialized = False

        sdlr = self.model.get_scheduler()
        sdlr.add_callback('schedule-cleared', self.clear_schedule_cb)
        sdlr.add_callback('schedule-added', self.new_schedule_cb)
        self.model.add_callback('schedule-selected', self.show_schedule_cb)

        # the solar system objects
        self.ss = [(common.moon, 'navajowhite2'),
                   (common.sun, 'darkgoldenrod1'),
                   (common.mercury, 'gray'), (common.venus, 'gray'),
                   (common.mars, 'mistyrose'), (common.jupiter, 'gray'),
                   (common.saturn, 'gray'), (common.uranus, 'gray'),
                   (common.neptune, 'gray'), (common.pluto, 'gray'),
                   ]
        # NOTE: these colors should match those in qplan.plots.airmass
        ## self.colors = ['blue', 'red', 'magenta', 'turquoise',
        ##                'salmon', 'plum', 'pink']
        self.colors = ['red', 'blue', 'green', 'cyan', 'magenta', 'yellow']
        self.telescope_pos = None

        self._wd = 600
        self._ht = 600

    def build_gui(self, container):

        zi = Viewers.CanvasView(logger=self.logger)
        zi.set_desired_size(self._wd, self._ht)
        zi.enable_autozoom('off')
        zi.enable_autocuts('off')

        zi.set_bg(0.95, 0.95, 0.95)
        zi.set_fg(0.25, 0.25, 0.75)
        self.viewer = zi

        p_canvas = zi.get_canvas()
        self.dc = p_canvas.get_draw_classes()
        self.canvas = self.dc.DrawingCanvas()
        p_canvas.add(self.canvas)
        self.initialize_plot()

        bd = zi.get_bindings()
        bd.enable_zoom(True)
        bd.enable_pan(True)

        iw = Viewers.GingaViewerWidget(zi)

        container.set_margins(2, 2, 2, 2)
        container.set_spacing(4)

        container.add_widget(iw, stretch=1)

    def _trans_targets(self, targets):
        sdlr = self.model.get_scheduler()
        _azalts = []
        # TODO: see if this can be done in a vector calculation
        for target, start_time, text, color in targets:
            info = target.calc(sdlr.site, start_time)
            if info.alt_deg > 0:
                _azalts.append((info.az_deg, info.alt_deg, text, color))
        return _azalts

    def initialize_plot(self):
        self.canvas.delete_object_by_tag('elev')

        objs = []

        # plot circles
        els = [85, 70, 50, 30, 15]
        #els.insert(0, 89)
        # plot circles
        objs.append(self.dc.Circle(0, 0, 90, color='black', linewidth=2,
                                   fill=True, fillcolor='palegreen1',
                                   fillalpha=0.5))

        objs.append(self.dc.Circle(0, 0, 1, color='darkgreen', linewidth=1))
        t = -75
        for el in els:
            r = (90 - el)
            r2 = r + 1
            objs.append(self.dc.Circle(0, 0, r, color='darkgreen'))
            x, y = p2r(r, t)
            objs.append(self.dc.Text(x, y, "{}".format(el), color='black',
                                     fontscale=True, fontsize=6))

        # plot lines
        for r1, t1, r2, t2 in [(90, 90, 90, -90), (90, 45, 90, -135),
                               (90, 0, 90, -180), (90, -45, 90, 135)]:
            x1, y1 = p2r(r1, t1)
            x2, y2 = p2r(r2, t2)
            objs.append(self.dc.Line(x1, y1, x2, y2, color='darkgreen'))

        # plot degrees
        for r, t in [(92, 0), (92, 45), (92, 90), (98, 135),
                     (100, 180), (100, 225), (95, 270), (92, 315)]:
            ang = (t + 90) % 360
            x, y = p2r(r, t)
            objs.append(self.dc.Text(x, y, "{}\u00b0".format(ang),
                                     fontscale=True, fontsize=6, color='black'))

        # plot compass directions
        for r, t, txt in [(110, 0, 'W'), (100, 90, 'N'),
                          (110, 180, 'E'), (100, 270, 'S')]:
            x, y = p2r(r, t)
            objs.append(self.dc.Text(x, y, txt, color='black', fontscale=True,
                                fontsize=14))

        o = self.dc.CompoundObject(*objs)
        self.canvas.add(o, tag='elev')

        self.viewer.set_limits([(-100, -100), (100, 100)])
        self.viewer.zoom_fit()

    def clear_plot(self):
        self.canvas.delete_object_by_tag('targets')
        self.canvas.delete_object_by_tag('ss')

    def plot_targets(self, targets, tag):
        self.canvas.delete_object_by_tag(tag)

        objs = []
        i = 0
        for az, alt, txt, color in targets:
            t, r = map_azalt(az, alt)
            x, y = p2r(r, t)
            objs.append(self.dc.Point(x, y, radius=1, style='circle',
                                      color=color, fillcolor=color,
                                      fill=True, fillalpha=0.5))
            objs.append(self.dc.Text(x, y, txt, color=color, fontscale=True,
                                     fontsize=8))

        o = self.dc.CompoundObject(*objs)
        self.canvas.add(o, tag=tag)

    def show_schedule_cb(self, model, schedule):
        try:
            info = self.schedules[schedule]

        except KeyError:
            return True

        # make slew plot
        self.logger.debug("plotting slew map")
        #self.view.gui_call(self.clear_targets)

        # plot a subset of the targets
        idx = int((self.controller.idx_tgt_plots / 100.0) * len(info.targets))
        num_tgts = self.controller.num_tgt_plots
        tgt_subset = info.targets[idx:idx+num_tgts]
        targets = self._trans_targets(tgt_subset)
        self.view.gui_call(self.plot_targets, targets, 'targets')

        # plot the current location of solar system objects
        start_time = tgt_subset[0][1]
        self.view.gui_call(self.plot_ss, start_time=start_time)

        # plot last known telescope position, if we know it
        if self.telescope_pos is not None:
            self.plot_telescope(*self.telescope_pos)

        return True

    def add_schedule(self, schedule):
        target_list = []
        i, j = 0, 0

        for slot in schedule.slots:
            ob = slot.ob
            if ob != None:
                if not ob.derived:
                    # not an OB generated to serve another OB
                    i += 1
                    #txt = "%d [%s]" % (i, ob.target.name)
                    txt = "%d [%s]" % (i, ob.name)
                    #txt = "%d" % (i)
                    color = self.colors[j]
                    j = (j + 1) % len(self.colors)
                    target_list.append((ob.target, slot.start_time, txt,
                                        color))

        self.schedules[schedule] = Bunch.Bunch(targets=target_list)
        return True

    def plot_ss(self, start_time=None):
        if start_time is None:
            sdlr = model.get_scheduler()
            start_time = datetime.now(tz=sdlr.timezone)
        ss_objs = [(tgt, start_time, tgt.name, color)
                   for tgt, color in self.ss]
        targets = self._trans_targets(ss_objs)
        self.view.gui_call(self.plot_targets, targets, 'ss')

    def plot_telescope(self, az, alt):
        self.canvas.delete_object_by_tag('telescope')

        t, r = map_azalt(az, alt)
        x, y = p2r(r, t)
        color = 'brown'
        objs = []
        objs.append(self.dc.Point(x, y, radius=2, style='plus',
                                  linewidth=2, color=color))
        objs.append(self.dc.Text(x, y, "Telescope", color=color))
        o = self.dc.CompoundObject(*objs)
        self.canvas.add(o, tag='telescope')

    def set_telescope_position(self, az, alt):
        self.telescope_pos = (az, alt)
        self.view.gui_do(self.plot_telescope, az, alt)

    def new_schedule_cb(self, sdlr, schedule):
        self.add_schedule(schedule)
        return True

    def clear_schedule_cb(self, sdlr):
        self.view.gui_call(self.clear_plot)
        return True


def p2r(r, t):
    t_rad = np.radians(t)
    x = r * np.cos(t_rad)
    y = r * np.sin(t_rad)
    return (x, y)

def map_azalt(az, alt):
    az = az % 360.0
    return az + 90.0, 90.0 - alt

#END
