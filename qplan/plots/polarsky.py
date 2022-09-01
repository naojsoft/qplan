import math
from datetime import datetime

import matplotlib as mpl
from matplotlib import rc

from ginga.util import plots

class AZELPlot(plots.Plot):

    def __init__(self, width, height, logger=None):
        super(AZELPlot, self).__init__(width=width, height=height,
                                       logger=logger)

        # radar green, solid grid lines
        rc('grid', color='#316931', linewidth=1, linestyle='-')
        rc('xtick', labelsize=10)
        rc('ytick', labelsize=10)

        # altitude increments, by degree
        self.alt_inc_deg = 15

        # colors used for successive points
        self.colors = ['r', 'b', 'g', 'c', 'm', 'y']

    def setup(self):
        kwargs = dict(projection='polar')
        if plots.MPL_GE_2_0:
            kwargs['facecolor'] = '#d5de9c'
        else:
            kwargs['axisbg'] = '#d5de9c'
        ax = self.fig.add_axes([0.1, 0.1, 0.8, 0.8], **kwargs)
        self.ax = ax

        # don't clear plot when we call plot()
        # TODO: remove--this is supposedly the default and call is deprecated
        #ax.hold(True)
        #ax.set_title("Slew order", fontsize=14)
        self.orient_plot()

    def get_figure(self):
        return self.fig

    def get_ax(self):
        return self.ax

    def clear(self):
        self.ax.cla()
        self.redraw()

    def map_azalt(self, az, alt):
        az = az % 360.0
        return (math.radians(az - 180.0), 90.0 - alt)

    def orient_plot(self):
        ax = self.ax
        # Orient plot for Subaru telescope
        ax.set_theta_zero_location("S")
        #ax.set_theta_direction(-1)
        ax.set_theta_direction(1)

        # standard polar projection has radial plot running 0 to 90,
        # inside to outside.
        # Adjust radius so it goes 90 at the center to 0 at the perimeter
        alts = list(range(0, 90, self.alt_inc_deg))
        # Redefine yticks and labels
        ax.set_yticks(alts)
        alts_r = list(range(90, 0, -self.alt_inc_deg))
        ax.set_yticklabels([str(i) for i in alts_r])
        # maximum altitude of 90.0
        ax.set_rmax(90.0)
        ax.grid(True)

        # add compass annotations
        ## for az, d in ((0.0, 'S'), (90.0, 'W'), (180.0, 'N'), (270.0, 'E')):
        ##     ax.annotate(d, xy=self.map_azalt(az, 0.0), textcoords='data')
        ax.annotate('W', (1.08, 0.5), textcoords='axes fraction',
                    fontsize=16)
        ax.annotate('E', (-0.1, 0.5), textcoords='axes fraction',
                    fontsize=16)
        ax.annotate('N', (0.5, 1.08), textcoords='axes fraction',
                    fontsize=16)
        ax.annotate('S', (0.5, -0.08), textcoords='axes fraction',
                    fontsize=16)

    def redraw(self):
        self.orient_plot()

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()

    def plot_azalt(self, az, alt, name, color, marker='o'):
        az, alt = self.map_azalt(az, alt)
        ax = self.ax
        ax.plot([az], [alt], color=color, marker=marker)
        ax.annotate(name, (az, alt))

        self.redraw()

    def plot_coords(self, coords):

        ax = self.ax
        lstyle = 'o'

        for i, tup in enumerate(coords):
            color = self.colors[i % len(self.colors)]
            lc = color + lstyle

            # alt: invert the radial axis
            az, alt = self.map_azalt(tup[0], tup[1])
            name = tup[2]
            ax.plot([az], [alt], lc)
            ax.annotate(name, (az, alt))

        self.redraw()

    def plot_azel(self, coords):
        self.plot_coords(coords)

    def _plot_target(self, observer, target, time_start, color):
        try:
            info = target.calc(observer, time_start)
        except Exception as e:
            print(str(e))
        az, alt = self.map_azalt(info.az_deg, info.alt_deg)
        self.ax.plot([az], [alt], 'o', color=color)
        self.ax.annotate(target.name, (az, alt))
        self.redraw()

    def plot_target(self, observer, target, time_start, color):
        self._plot_target(observer, target, time_start, color)
        self.redraw()

    def plot_targets(self, observer, targets, time_start, colors):
        i = 0
        for target in targets:
            self._plot_target(observer, target, time_start, colors[i])
            i = (i+1) % len(colors)
        self.redraw()

if __name__ == '__main__':
    from qplan import entity, common
    from qplan.util.site import get_site

    from ginga import toolkit
    toolkit.use('qt')

    from ginga.gw import Widgets, Plot

    plot = AZELPlot(1000, 1000)
    plot.setup()

    app = Widgets.Application()
    topw = app.make_window()
    plotw = Plot.PlotWidget(plot)
    topw.set_widget(plotw)
    topw.add_callback('close', lambda w: w.delete())
    topw.show()

    plot.plot_coords([(-210.0, 60.43, "telescope"),])
    tgt3 = entity.StaticTarget(name="Bootes", ra="14:31:45.40",
                               dec="+32:28:38.50")
    site = get_site('subaru')
    tz = site.tz_local

    start_time = datetime.strptime("2015-03-27 20:05:00",
                                   "%Y-%m-%d %H:%M:%S")
    start_time = start_time.replace(tzinfo=site.tz_local)
    plot.plot_targets(site, [common.moon, common.sun, tgt3],
                      start_time, ['white', 'yellow', 'green'])

    app.mainloop()

#END
