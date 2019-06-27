#
# plots.py -- does matplotlib plots needed for queue tools
#
# Eric Jeschke (eric@naoj.org)
#
# Some code based on "Observer" module by Daniel Magee
#   Copyright (c) 2008 UCO/Lick Observatory.
#
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
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

    def plot_airmass(self, site, tgt_data, tz, plot_moon_distance=False,
                      show_target_legend=False):
        self._plot_airmass(self.fig, site, tgt_data, tz,
                           plot_moon_distance=plot_moon_distance,
                           show_target_legend=show_target_legend)

    def _plot_airmass(self, figure, site, tgt_data, tz,
                      plot_moon_distance=False,
                      show_target_legend=False):
        """
        Plot into `figure` an airmass chart using target data from `info`
        with time plotted in timezone `tz` (a tzinfo instance).
        """

        # set major ticks to hours
        majorTick = mpl_dt.HourLocator(tz=tz)
        majorFmt = mpl_dt.DateFormatter('%Hh', tz=tz)
        # set minor ticks to 15 min intervals
        minorTick = mpl_dt.MinuteLocator(list(range(0,59,15)), tz=tz)

        figure.clf()
        ax1 = figure.add_subplot(111)
        self.ax = ax1
        if show_target_legend:
            figure.set_tight_layout(False)
            figure.subplots_adjust(left=0.05, right=0.65, bottom=0.12, top=0.95)

        #lstyle = 'o'
        lstyle = '-'
        lt_data = [info.ut.astimezone(tz) for info in tgt_data[0].history]

        # we don't know what date "site" is currently initialized to,
        # so find out the date of the first target
        localdate = lt_data[0].astimezone(tz)

        min_interval = 12  # hour/5min
        mt = lt_data[0:-1:min_interval]
        targets, legend = [], []

        # plot targets airmass vs. time
        for i, info in enumerate(tgt_data):
            am_data = numpy.array([t.airmass for t in info.history])
            am_min = numpy.argmin(am_data)
            am_data_dots = am_data
            color = self.colors[i % len(self.colors)]
            lc = color + lstyle
            # ax1.plot_date(lt_data, am_data, lc, linewidth=1.0, alpha=0.3, aa=True, tz=tz)
            lg = ax1.plot_date(lt_data, am_data_dots, lc, linewidth=2.0,
                               aa=True, tz=tz)
            #xs, ys = mpl.mlab.poly_between(lt_data, 2.02, am_data)
            #ax1.fill(xs, ys, facecolor=self.colors[i], alpha=0.2)
            legend.extend(lg)

            targets.append("{0} {1} {2}".format(info.target.name, info.target.ra,
                                                info.target.dec))

            if plot_moon_distance:
                am_interval = am_data[0:-1:min_interval]
                moon_sep = numpy.array([tgt.moon_sep for tgt in info.history])
                moon_sep = moon_sep[0:-1:min_interval]

                # plot moon separations
                for x, y, v in zip(mt, am_interval, moon_sep):
                    if y < 0:
                        continue
                    ax1.text(x, y, '%.1f' %v, fontsize=7,  ha='center', va='bottom')
                    ax1.plot_date(x, y, 'ko', ms=3)

            # plot object label
            targname = info.target.name
            ax1.text(mpl_dt.date2num(lt_data[am_data.argmin()]),
                     am_data.min() + 0.08, targname.upper(), color=color,
                     ha='center', va='center')

        # legend target list
        if show_target_legend:
            self.fig.legend(legend, targets, 'upper right', fontsize=9, framealpha=0.5,
                            frameon=True, ncol=1, bbox_to_anchor=[0.3, 0.865, .7, 0.1])

        ax1.set_ylim(2.02, 0.98)
        ax1.set_xlim(lt_data[0], lt_data[-1])
        ax1.xaxis.set_major_locator(majorTick)
        ax1.xaxis.set_minor_locator(minorTick)
        ax1.xaxis.set_major_formatter(majorFmt)
        labels = ax1.get_xticklabels()
        ax1.grid(True, color='#999999')

        self._plot_twilight(ax1, site, localdate, tz,
                            show_legend=show_target_legend)

        # plot current hour
        lo = datetime.now(tz)
        hi = lo + timedelta(0, 3600.0)
        if lt_data[0] < lo < lt_data[-1]:
            self._plot_current_time(ax1, lo, hi)

        # label axes
        title = 'Airmass for the night of {}'.format(localdate.strftime("%Y-%m-%d"))
        ax1.set_title(title)
        ax1.set_xlabel(tz.tzname(None))
        ax1.set_ylabel('Airmass')

        # Plot moon altitude and degree scale
        ax2 = ax1.twinx()
        moon_data = numpy.array([t.moon_alt for t in tgt_data[0].history])
        #moon_illum = site.moon_phase()
        ax2.plot_date(lt_data, moon_data, '#666666', linewidth=2.0,
                      alpha=0.5, aa=True, tz=tz)
        ax2.set_ylabel('Moon Altitude (deg)', color='#666666')
        ax2.set_ylim(0, 90)
        ax2.set_xlim(lt_data[0], lt_data[-1])
        ax2.xaxis.set_major_locator(majorTick)
        ax2.xaxis.set_minor_locator(minorTick)
        ax2.xaxis.set_major_formatter(majorFmt)
        ax2.set_xlabel('')
        ax2.yaxis.tick_right()

        # drawing the line of middle of the night
        self._middle_night(ax1, site, localdate)

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()


    def plot_altitude(self, site, tgt_data, tz, plot_moon_distance=False,
                      show_target_legend=False):
        self._plot_altitude(self.fig, site, tgt_data, tz,
                            plot_moon_distance=plot_moon_distance,
                            show_target_legend=show_target_legend)

    def _plot_altitude(self, figure, site, tgt_data, tz,
                       plot_moon_distance=False,
                       show_target_legend=False):
        """
        Plot into `figure` an altitude chart using target data from `info`
        with time plotted in timezone `tz` (a tzinfo instance).
        """
        # set major ticks to hours
        majorTick = mpl_dt.HourLocator(tz=tz)
        majorFmt = mpl_dt.DateFormatter('%Hh', tz=tz)
        # set minor ticks to 15 min intervals
        minorTick = mpl_dt.MinuteLocator(list(range(0, 59, 15)), tz=tz)

        figure.clf()
        ax1 = figure.add_subplot(111)
        self.ax = ax1
        if show_target_legend:
            figure.set_tight_layout(False)
            figure.subplots_adjust(left=0.05, right=0.65, bottom=0.12, top=0.95)

        #lstyle = 'o'
        lstyle = '-'
        lt_data = [t.ut.astimezone(tz) for t in tgt_data[0].history]

        # we don't know what date "site" is currently initialized to,
        # so get the date of the first target
        localdate = lt_data[0].astimezone(tz)

        min_interval = 12  # hour/5min
        mt = lt_data[0:-1:min_interval]
        targets, legend = [], []

        # plot targets elevation vs. time
        for i, info in enumerate(tgt_data):
            alt_data = numpy.array([t.alt_deg for t in info.history])
            alt_min = numpy.argmin(alt_data)
            alt_data_dots = alt_data
            color = self.colors[i % len(self.colors)]
            lc = color + lstyle
            # ax1.plot_date(lt_data, alt_data, lc, linewidth=1.0, alpha=0.3, aa=True, tz=tz)
            lg = ax1.plot_date(lt_data, alt_data_dots, lc, linewidth=2.0,
                               aa=True, tz=tz)
            #xs, ys = mpl.mlab.poly_between(lt_data, 2.02, alt_data)
            #ax1.fill(xs, ys, facecolor=self.colors[i], alpha=0.2)
            legend.extend(lg)

            targets.append("{0} {1} {2}".format(info.target.name, info.target.ra,
                                                info.target.dec))

            if plot_moon_distance:
                alt_interval = alt_data[0:-1:min_interval]
                moon_sep = numpy.array([tgt.moon_sep for tgt in info.history])
                moon_sep = moon_sep[0:-1:min_interval]

                # plot moon separations
                for x, y, v in zip(mt, alt_interval, moon_sep):
                    if y < 0:
                        continue
                    ax1.text(x, y, '%.1f' %v, fontsize=7,  ha='center', va='bottom')
                    ax1.plot_date(x, y, 'ko', ms=3)

            # plot object label
            targname = info.target.name
            ax1.text(mpl_dt.date2num(lt_data[alt_data.argmax()]),
                     alt_data.max() + 4.0, targname, color=color,
                     ha='center', va='center')

        # legend target list
        if show_target_legend:
            self.fig.legend(legend, targets, 'upper right', fontsize=9, framealpha=0.5,
                            frameon=True, ncol=1, bbox_to_anchor=[0.3, 0.865, .7, 0.1])

        ax1.set_ylim(0.0, 90.0)
        ax1.set_xlim(lt_data[0], lt_data[-1])
        ax1.xaxis.set_major_locator(majorTick)
        ax1.xaxis.set_minor_locator(minorTick)
        ax1.xaxis.set_major_formatter(majorFmt)
        labels = ax1.get_xticklabels()
        ax1.grid(True, color='#999999')

        # label axes
        title = 'Visibility for the night of {}'.format(localdate.strftime("%Y-%m-%d"))
        ax1.set_title(title)
        # TODO: datautil.tzinfo does not seem to have a readable timezone name
        #ax1.set_xlabel(tz.tzname(None))
        ax1.set_xlabel('HST')
        ax1.set_ylabel('Altitude')

        # Plot moon trajectory and illumination
        moon_data = numpy.array([t.moon_alt for t in tgt_data[0].history])
        illum_time = lt_data[moon_data.argmax()]
        moon_illum = site.moon_phase(date=illum_time)
        moon_color = '#666666'
        moon_name = "Moon (%.2f %%)" % (moon_illum*100)
        ax1.plot_date(lt_data, moon_data, moon_color, linewidth=2.0,
                      alpha=0.5, aa=True, tz=tz)
        ax1.text(mpl_dt.date2num(illum_time),
                 moon_data.max() + 4.0, moon_name, color=moon_color,
                 ha='center', va='center')

        # Plot airmass scale
        altitude_ticks = numpy.array([20, 30, 40, 50, 60, 70, 80, 90])
        airmass_ticks = 1.0/numpy.cos(numpy.radians(90 - altitude_ticks))
        airmass_ticks = ["%.3f" % n for n in airmass_ticks]

        ax2 = ax1.twinx()
        #ax2.set_ylim(None, 0.98)
        #ax2.set_xlim(lt_data[0], lt_data[-1])
        ax2.set_yticks(altitude_ticks)
        ax2.set_yticklabels(airmass_ticks)
        ax2.set_ylim(ax1.get_ylim())
        ax2.set_ylabel('Airmass')
        ax2.set_xlabel('')
        ax2.yaxis.tick_right()

        # plot moon label
        targname = "moon"
        ## ax1.text(mpl_dt.date2num(moon_data[moon_data.argmax()]),
        ##          moon_data.max() + 0.08, targname.upper(), color=color,
        ##          ha='center', va='center')

        # plot lower and upper safe limits for clear observing
        min_alt, max_alt = 30.0, 75.0
        self._plot_limits(ax1, min_alt, max_alt)

        self._plot_twilight(ax1, site, localdate, tz,
                            show_legend=show_target_legend)

        # plot current hour
        lo = datetime.now(tz)
        hi = lo + timedelta(0, 3600.0)
        if lt_data[0] < lo < lt_data[-1]:
            self._plot_current_time(ax1, lo, hi)

        # drawing the line of middle of the night
        self._middle_night(ax1, site, localdate)

        # plot moon's position at midnight
        #self._moon_position(ax1, site)

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()

    def _middle_night(self, ax, site, localdate):
        # night center
        middle_night = site.night_center(date=localdate)

        ymin, ymax = ax.get_ylim()

        ax.vlines(middle_night, ymin, ymax, colors='blue',
                  linestyles='dashed', label='Night center')

    def _plot_twilight(self, ax, site, localdate, tz, show_legend=False):
        # plot sunset
        t = site.sunset(date=localdate).astimezone(tz)

        # plot evening twilight 6/12/18 degrees
        et6 = site.evening_twilight_6(t).astimezone(tz)
        et12 = site.evening_twilight_12(t).astimezone(tz)
        et18 = site.evening_twilight_18(t).astimezone(tz)

        ymin, ymax = ax.get_ylim()
        # civil twilight 6 degree
        ct = ax.axvspan(t, et6, facecolor='#FF6F00', lw=None, ec='none', alpha=0.35)
        # nautical twilight 12 degree
        nt = ax.axvspan(et6, et12, facecolor='#947DC0', lw=None, ec='none', alpha=0.5)
        # astronomical twilight 18 degree
        at = ax.axvspan(et12, et18, facecolor='#3949AB', lw=None, ec='none', alpha=0.65)

        ss = ax.vlines(t, ymin, ymax, colors=['red'],
                       linestyles=['dashed'], label='Sunset')

        if show_legend:
            sunset = "Sunset {}".format(t.strftime("%H:%M:%S"))
            civil_twi = "Civil Twi {}".format(et6.strftime("%H:%M:%S"))
            nautical_twi = "Nautical Twi {}".format(et12.strftime("%H:%M:%S"))
            astro_twi = "Astronomical Twi {}".format(et18.strftime("%H:%M:%S"))

            self.fig.legend((ss, ct, nt, at), (sunset, civil_twi, nautical_twi, astro_twi),
                            'upper left', fontsize=7, framealpha=0.5,
                            bbox_to_anchor=[0.045, -0.02, .7, 0.113])

        # plot morning twilight 6/12/18 degrees
        mt6 = site.morning_twilight_6(et6).astimezone(tz)
        mt12 = site.morning_twilight_12(et12).astimezone(tz)
        mt18 = site.morning_twilight_18(et18).astimezone(tz)

        # plot sunrise
        t2 = site.sunrise(mt18).astimezone(tz)

        # astronomical twilight 18 degree
        at = ax.axvspan(mt18, mt12, facecolor='#3949AB', lw=None, ec='none', alpha=0.65)
        # nautical twilight 12 degree
        nt = ax.axvspan(mt12, mt6, facecolor='#947DC0', lw=None, ec='none', alpha=0.5)
        # civil twilight 6 degree
        ct = ax.axvspan(mt6, t2, facecolor='#FF6F00', lw=None, ec='none', alpha=0.35)

        sr = ax.vlines(t2, ymin, ymax, colors=['red'],
                   linestyles=['dashed'], label='Sunrise')

        if show_legend:
            sunrise = "Sunrise {}".format(t2.strftime("%H:%M:%S"))
            civil_twi = "Civil Twi {}".format(mt6.strftime("%H:%M:%S"))
            nautical_twi = "Nautical Twi {}".format(mt12.strftime("%H:%M:%S"))
            astro_twi = "Astronomical Twi {}".format(mt18.strftime("%H:%M:%S"))

            self.fig.legend((sr, ct, nt, at), (sunrise, civil_twi, nautical_twi, astro_twi),
                            fontsize=7, framealpha=0.5,
                            bbox_to_anchor=[-0.043, -0.02, .7, 0.113])

    def _plot_current_time(self, ax, lo, hi):
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
    toolkit.use('qt5')

    from ginga.gw import Widgets, Plot
    plot = AirMassPlot(1200, 740)

    outfile = None
    if len(sys.argv) > 1:
        outfile = sys.argv[1]

    if outfile is None:
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
    start_time = start_time.replace(tzinfo=tz)
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

    ## plot.plot_airmass(site, target_data, tz, show_target_legend=True,
    ##                   plot_moon_distance=True)
    plot.plot_altitude(site, target_data, tz, show_target_legend=True,
                       plot_moon_distance=True)

    if outfile is None:
        topw.show()
    else:
        plot.fig.savefig(outfile)

    app.mainloop()

#END
