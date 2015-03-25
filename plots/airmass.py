#
# plots.py -- does matplotlib plots needed for queue tools
# 
# Eric Jeschke (eric@naoj.org)
#
from __future__ import print_function
from datetime import datetime, timedelta
#import pytz
import numpy

import matplotlib.dates as mpl_dt
import matplotlib as mpl

from ginga.misc import Bunch


def plot_airmass(figure, info, tz):
    """
    Plot into `figure` an airmass chart using target data from `info`
    with time plotted in timezone `tz` (a tzinfo instance).
    """
    site = info.site
    tgt_data = info.target_data
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
    
    colors = ['r', 'b', 'g', 'c', 'm', 'y']
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
        color = colors[i % len(colors)]
        lc = color + lstyle
        # ax1.plot_date(lt_data, am_data, lc, linewidth=1.0, alpha=0.3, aa=True, tz=tz)
        # xs, ys = mpl.mlab.poly_between(lt_data, 2.02, am_data)
        # ax1.fill(xs, ys, facecolor=colors[i], alpha=0.2)
        lstyle = 'o'
        lc = color + lstyle
        ax1.plot_date(lt_data, am_data_dots, lc, linewidth=1.0, aa=True, tz=tz)

        # plot object label
        targname = info.target.name
        ax1.text(mpl_dt.date2num(lt_data[am_data.argmin()]), am_data.min() + 0.08, targname.upper(), color=color, ha='center', va='center')

    ax1.set_ylim(2.02, 0.98)
    ax1.set_xlim(lt_data[0], lt_data[-1])
    ax1.xaxis.set_major_locator(majorTick)
    ax1.xaxis.set_minor_locator(minorTick)
    ax1.xaxis.set_major_formatter(majorFmt)
    labels = ax1.get_xticklabels()
    ax1.grid(True, color='#999999')

    # plot current hour
    lo = datetime.now(tz)
    #lo = datetime.now(tz=tz)
    hi = lo + timedelta(0, 3600.0)
    if lt_data[0] < lo < lt_data[-1]:
        ax1.axvspan(lo, hi, facecolor='#7FFFD4', alpha=0.25)

    # label axes
    localdate = lt_data[0].astimezone(tz).strftime("%Y-%m-%d")
    title = 'Airmass for the night of %s' % (localdate)
    ax1.set_title(title)
    ax1.set_xlabel(tz.tzname(None))
    ax1.set_ylabel('Airmass')

    # Plot moon altitude and degree scale
    ax2 = ax1.twinx()
    moon_data = numpy.array(map(lambda info: info.moon_alt, tgt_data[0].history))
    moon_illum = site.moon_phase()
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


#END
