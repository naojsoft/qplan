#
# plots.py -- does matplotlib plots needed for queue tools
#
# Eric Jeschke (eric@naoj.org)
#
# Some code based on "Observer" module by Daniel Magee
#   Copyright (c) 2008 UCO/Lick Observatory.
#
from __future__ import print_function
from datetime import datetime, timedelta
import pytz
import numpy

import matplotlib.dates as mpl_dt
import matplotlib as mpl
from matplotlib.ticker import FormatStrFormatter

from ginga.misc import Bunch
from ginga.util import plots

class AirMassPlot(plots.Plot):

    def __init__(self, width, height, logger=None):
        super(AirMassPlot, self).__init__(width=width, height=height,
                                          logger=logger)

        # time increments, by minute
        self.time_inc_min = 15

        # colors used for successive points
        self.colors = ['r', 'b', 'g', 'c', 'm', 'y']

    def setup(self):
        pass

    def get_figure(self):
        return self.fig

    def clear(self):
        #self.ax.cla()
        self.fig.clf()

    def plot_airmass(self, site, tgt_data, tz):
        self._plot_airmass(self.fig, site, tgt_data, tz)


    def _plot_airmass(self, figure, site, tgt_data, tz):
        """
        Plot into `figure` an airmass chart using target data from `info`
        with time plotted in timezone `tz` (a tzinfo instance).
        """
        ## site = info.site
        ## tgt_data = info.target_data
        # Urk! This seems to be necessary even though we are plotting
        # python datetime objects with timezone attached and setting
        # date formatters with the timezone
        tz_str = tz.tzname(None)
        mpl.rcParams['timezone'] = tz_str

        # set major ticks to hours
        majorTick = mpl_dt.HourLocator(tz=tz)
        majorFmt = mpl_dt.DateFormatter('%Hh')
        # set minor ticks to 15 min intervals
        minorTick = mpl_dt.MinuteLocator(range(0,59,15), tz=tz)

        figure.clf()
        ax1 = figure.add_subplot(111)

        #lstyle = 'o'
        lstyle = '-'
        lt_data = map(lambda info: info.ut.astimezone(tz),
                      tgt_data[0].history)
        # sanity check on dates in preferred timezone
        ## for dt in lt_data[:10]:
        ##     print(dt.strftime("%Y-%m-%d %H:%M:%S"))

        # plot targets airmass vs. time
        for i, info in enumerate(tgt_data):
            am_data = numpy.array(map(lambda info: info.airmass, info.history))
            am_min = numpy.argmin(am_data)
            am_data_dots = am_data
            color = self.colors[i % len(self.colors)]
            lc = color + lstyle
            # ax1.plot_date(lt_data, am_data, lc, linewidth=1.0, alpha=0.3, aa=True, tz=tz)
            ax1.plot_date(lt_data, am_data_dots, lc, linewidth=2.0,
                          aa=True, tz=tz)
            #xs, ys = mpl.mlab.poly_between(lt_data, 2.02, am_data)
            #ax1.fill(xs, ys, facecolor=self.colors[i], alpha=0.2)

            # plot object label
            targname = info.target.name
            ax1.text(mpl_dt.date2num(lt_data[am_data.argmin()]),
                     am_data.min() + 0.08, targname.upper(), color=color,
                     ha='center', va='center')

        ax1.set_ylim(2.02, 0.98)
        ax1.set_xlim(lt_data[0], lt_data[-1])
        ax1.xaxis.set_major_locator(majorTick)
        ax1.xaxis.set_minor_locator(minorTick)
        ax1.xaxis.set_major_formatter(majorFmt)
        labels = ax1.get_xticklabels()
        ax1.grid(True, color='#999999')

        self._plot_twilight(ax1, site, tz)

        # plot current hour
        lo = datetime.now(tz)
        hi = lo + timedelta(0, 3600.0)
        if lt_data[0] < lo < lt_data[-1]:
            self._plot_current_time(ax1, lo, hi)

        # label axes
        localdate = lt_data[0].astimezone(tz).strftime("%Y-%m-%d")
        title = 'Airmass for the night of %s' % (localdate)
        ax1.set_title(title)
        ax1.set_xlabel(tz.tzname(None))
        ax1.set_ylabel('Airmass')

        # Plot moon altitude and degree scale
        ax2 = ax1.twinx()
        moon_data = numpy.array(map(lambda info: info.moon_alt,
                                    tgt_data[0].history))
        #moon_illum = site.moon_phase()
        ax2.plot_date(lt_data, moon_data, '#666666', linewidth=2.0,
                      alpha=0.5, aa=True, tz=tz)
        mxs, mys = mpl.mlab.poly_between(lt_data, 0, moon_data)
        # ax2.fill(mxs, mys, facecolor='#666666', alpha=moon_illum)
        ax2.set_ylabel('Moon Altitude (deg)', color='#666666')
        ax2.set_ylim(0, 90)
        ax2.set_xlim(lt_data[0], lt_data[-1])
        ax2.xaxis.set_major_locator(majorTick)
        ax2.xaxis.set_minor_locator(minorTick)
        ax2.xaxis.set_major_formatter(majorFmt)
        ax2.set_xlabel('')
        ax2.yaxis.tick_right()

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()


    def plot_altitude(self, site, tgt_data, tz):
        self._plot_altitude(self.fig, site, tgt_data, tz)


    def _plot_altitude(self, figure, site, tgt_data, tz):
        """
        Plot into `figure` an altitude chart using target data from `info`
        with time plotted in timezone `tz` (a tzinfo instance).
        """
        ## site = info.site
        ## tgt_data = info.target_data
        # Urk! This seems to be necessary even though we are plotting
        # python datetime objects with timezone attached and setting
        # date formatters with the timezone
        tz_str = tz.tzname(None)
        mpl.rcParams['timezone'] = tz_str

        # set major ticks to hours
        majorTick = mpl_dt.HourLocator(tz=tz)
        majorFmt = mpl_dt.DateFormatter('%Hh')
        # set minor ticks to 15 min intervals
        minorTick = mpl_dt.MinuteLocator(range(0,59,15), tz=tz)

        figure.clf()
        ax1 = figure.add_subplot(111)

        #lstyle = 'o'
        lstyle = '-'
        lt_data = map(lambda info: info.ut.astimezone(tz),
                      tgt_data[0].history)
        # sanity check on dates in preferred timezone
        ## for dt in lt_data[:10]:
        ##     print(dt.strftime("%Y-%m-%d %H:%M:%S"))

        # plot targets elevation vs. time
        for i, info in enumerate(tgt_data):
            alt_data = numpy.array(map(lambda info: info.alt_deg, info.history))
            alt_min = numpy.argmin(alt_data)
            alt_data_dots = alt_data
            color = self.colors[i % len(self.colors)]
            lc = color + lstyle
            # ax1.plot_date(lt_data, alt_data, lc, linewidth=1.0, alpha=0.3, aa=True, tz=tz)
            ax1.plot_date(lt_data, alt_data_dots, lc, linewidth=2.0,
                          aa=True, tz=tz)
            #xs, ys = mpl.mlab.poly_between(lt_data, 2.02, alt_data)
            #ax1.fill(xs, ys, facecolor=self.colors[i], alpha=0.2)

            # plot object label
            targname = info.target.name
            ax1.text(mpl_dt.date2num(lt_data[alt_data.argmax()]),
                     alt_data.max() + 4.0, targname.upper(), color=color,
                     ha='center', va='center')

        ax1.set_ylim(0.0, 90.0)
        ax1.set_xlim(lt_data[0], lt_data[-1])
        ax1.xaxis.set_major_locator(majorTick)
        ax1.xaxis.set_minor_locator(minorTick)
        ax1.xaxis.set_major_formatter(majorFmt)
        labels = ax1.get_xticklabels()
        ax1.grid(True, color='#999999')

        # label axes
        localdate = lt_data[0].astimezone(tz).strftime("%Y-%m-%d")
        title = 'Visibility for the night of %s' % (localdate)
        ax1.set_title(title)
        ax1.set_xlabel(tz.tzname(None))
        ax1.set_ylabel('Altitude')

        # Plot moon trajectory and illumination
        moon_data = numpy.array(map(lambda info: info.moon_alt,
                                    tgt_data[0].history))
        illum_time = lt_data[moon_data.argmax()]
        moon_illum = site.moon_phase(date=illum_time.astimezone(tz))
        moon_color = '#666666'
        moon_name = "Moon (%.2f %%)" % (moon_illum)
        ax1.plot_date(lt_data, moon_data, moon_color, linewidth=2.0,
                      alpha=0.5, aa=True, tz=tz)
        ax1.text(mpl_dt.date2num(illum_time),
                 moon_data.max() + 4.0, moon_name, color=moon_color,
                 ha='center', va='center')

        # Plot airmass scale
        altitude_ticks = numpy.array([20, 30, 40, 50, 60, 70, 80, 90])
        airmass_ticks = 1.0/numpy.cos(numpy.radians(90 - altitude_ticks))
        airmass_ticks = list(map(lambda n: "%.3f" % n, airmass_ticks))

        ax2 = ax1.twinx()
        #ax2.set_ylim(None, 0.98)
        #ax2.set_xlim(lt_data[0], lt_data[-1])
        ax2.set_yticks(altitude_ticks)
        ax2.set_yticklabels(airmass_ticks)
        ax2.set_ylim(ax1.get_ylim())
        ax2.set_ylabel('Airmass')
        ax2.set_xlabel('')
        ax2.yaxis.tick_right()

        ## mxs, mys = mpl.mlab.poly_between(lt_data, 0, moon_data)
        ## # ax2.fill(mxs, mys, facecolor='#666666', alpha=moon_illum)

        # plot moon label
        targname = "moon"
        ## ax1.text(mpl_dt.date2num(moon_data[moon_data.argmax()]),
        ##          moon_data.max() + 0.08, targname.upper(), color=color,
        ##          ha='center', va='center')

        # plot lower and upper safe limits for clear observing
        min_alt, max_alt = 30.0, 75.0
        self._plot_limits(ax1, min_alt, max_alt)

        self._plot_twilight(ax1, site, tz)

        # plot current hour
        lo = datetime.now(tz)
        hi = lo + timedelta(0, 3600.0)
        if lt_data[0] < lo < lt_data[-1]:
            self._plot_current_time(ax1, lo, hi)

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()

    def _plot_twilight(self, ax, site, tz):
        # plot sunset
        t = site.tz_utc.localize(site.sunset().datetime()).astimezone(tz)

        # plot evening twilight
        t2 = site.tz_utc.localize(site.evening_twilight_18(t).datetime()).astimezone(tz)

        #n, n2 = list(map(mpl_dt.date2num, [t, t2]))
        ymin, ymax = ax.get_ylim()
        ax.axvspan(t, t2, facecolor='#947DC0', alpha=0.20)
        ax.vlines(t, ymin, ymax, colors=['orange'],
                   linestyles=['dashed'], label='Sunset')
        ax.vlines(t2, ymin, ymax, colors=['orange'],
                   linestyles=['dashed'], label='Evening twilight')

        # plot morning twilight
        t = site.tz_utc.localize(site.morning_twilight_18(t2).datetime()).astimezone(tz)

        # plot sunrise
        t2 = site.tz_utc.localize(site.sunrise(t).datetime()).astimezone(tz)

        ax.axvspan(t, t2, facecolor='#947DC0', alpha=0.20)
        ax.vlines(t, ymin, ymax, colors=['orange'],
                   linestyles=['dashed'], label='Morning twilight')
        ax.vlines(t, ymin, ymax, colors=['orange'],
                   linestyles=['dashed'], label='Sunrise')

    def _plot_time(self, ax, lo, hi):
        ax.axvspan(lo, hi, facecolor='#7FFFD4', alpha=0.25)

    def _plot_limits(self, ax, lo_lim, hi_lim):
        ymin, ymax = ax.get_ylim()
        ax.axhspan(ymin, lo_lim, facecolor='#F9EB4E', alpha=0.20)

        ax.axhspan(hi_lim, ymax, facecolor='#F9EB4E', alpha=0.20)


if __name__ == '__main__':
    import sys
    from qplan import entity, common
    from qplan.util.site import get_site

    from ginga import toolkit
    toolkit.use('qt')

    from ginga.gw import Widgets, Plot
    plot = AirMassPlot(1000, 600)

    outfile = None
    if len(sys.argv) > 1:
        outfile = sys.argv[1]

    if outfile == None:
        app = Widgets.Application()
        topw = app.make_window()
        plotw = Plot.PlotWidget(plot)
        topw.set_widget(plotw)
        topw.add_callback('close', lambda w: w.delete())
    else:
        from ginga.aggw import Plot
        plotw = Plot.PlotWidget(plot)

    plot.setup()
    site = get_site('subaru')
    tz = site.tz_local

    start_time = datetime.strptime("2015-03-30 18:30:00",
                                   "%Y-%m-%d %H:%M:%S")
    start_time = tz.localize(start_time)
    t = start_time
    # if schedule starts after midnight, change start date to the
    # day before
    if 0 <= t.hour < 12:
        t -= timedelta(0, 3600*12)
    ndate = t.strftime("%Y/%m/%d")

    targets = []
    site.set_date(t)
    tgt = entity.StaticTarget(name='S5', ra='14:20:00.00', dec='48:00:00.00')
    targets.append(tgt)
    tgt = entity.StaticTarget(name='Sf', ra='09:40:00.00', dec='43:00:00.00')
    targets.append(tgt)
    tgt = entity.StaticTarget(name='Sm', ra='10:30:00.00', dec='36:00:00.00')
    targets.append(tgt)
    tgt = entity.StaticTarget(name='Sn', ra='15:10:00.00', dec='34:00:00.00')
    targets.append(tgt)

    # make airmass plot
    num_tgts = len(targets)
    target_data = []
    lengths = []
    if num_tgts > 0:
        for tgt in targets:
            info_list = site.get_target_info(tgt)
            target_data.append(Bunch.Bunch(history=info_list, target=tgt))
            lengths.append(len(info_list))

    # clip all arrays to same length
    min_len = min(*lengths)
    for il in target_data:
        il.history = il.history[:min_len]

    ## info = Bunch.Bunch(site=site, num_tgts=num_tgts,
    ##                    target_data=target_data)
    plot.plot_airmass(site, target_data, tz)

    if outfile == None:
        topw.show()
    else:
        plot.fig.savefig(outfile)

    app.mainloop()

#END
