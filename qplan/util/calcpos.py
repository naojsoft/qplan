#
# calcpos.py -- module for wrapping astronomical ephemeris calculations
#
import math

# third-party imports
import numpy as np
from datetime import datetime, timedelta
from dateutil import tz

# right now we just have pyephem...
import ephem

# Constants

#earth_radius = 6378160.0
# TODO: more precise calculation
#minute = 0.0006944444444444444


def alt2airmass(alt_deg):
    xp = 1.0 / math.sin(math.radians(alt_deg + 244.0/(165.0 + 47*alt_deg**1.1)))
    return xp

am_inv = []
for alt in range(0, 91):
    alt_deg = float(alt)
    am = alt2airmass(alt_deg)
    am_inv.append((am, alt_deg))

def airmass2alt(am):
    # TODO: horribly inefficient lookup--FIX!
    for (x, alt_deg) in am_inv:
        if x <= am:
            return alt_deg
    return 90.0

#### Classes ####


class Observer(object):
    """
    Observer
    """
    def __init__(self, name, timezone=None, longitude=None, latitude=None,
                 elevation=None, pressure=None, temperature=None,
                 date=None, description=None):
        super(Observer, self).__init__()
        self.name = name
        self.timezone = timezone
        self.longitude = longitude
        self.latitude = latitude
        self.elevation = elevation
        self.pressure = pressure
        self.temperature = temperature
        self.date = date
        self.horizon = -1 * np.sqrt(2 * elevation / ephem.earth_radius)
        if timezone is None:
            # default to UTC
            timezone = tz.UTC
        self.tz_local = timezone
        self.tz_utc = tz.UTC
        self.site = self.get_site(date=date)

        # used for sunset, sunrise calculations
        self.horizon6 = -1.0 * ephem.degrees('06:00:00.0')
        self.horizon12 = -1.0 * ephem.degrees('12:00:00.0')
        self.horizon18 = -1.0 * ephem.degrees('18:00:00.0')
        self.sun = ephem.Sun()
        self.moon = ephem.Moon()
        self.sun.compute(self.site)
        self.moon.compute(self.site)

    def get_site(self, date=None, horizon_deg=None):
        site = ephem.Observer()
        site.lon = self.longitude
        site.lat = self.latitude
        site.elevation = self.elevation
        site.pressure = self.pressure
        site.temp = self.temperature
        if horizon_deg != None:
            site.horizon = math.radians(horizon_deg)
        else:
            site.horizon = self.horizon
        site.epoch = 2000.0
        if date is None:
            date = datetime.utcnow().replace(tzinfo=self.tz_utc)
        site.date = ephem.Date(self.date_to_utc(date))
        return site

    def date_to_utc(self, date):
        """Convert a datetime to UTC.
        NOTE: If the datetime object is not timezone aware, it is
        assumed to be in the timezone of the observer.
        """
        if date.tzinfo is not None:
            # date is timezone-aware
            date = date.astimezone(self.tz_utc)

        else:
            # date is a naive date: assume expressed in local time
            date = date.replace(tzinfo=self.tz_local)
            # and converted to UTC
            date = date.astimezone(self.tz_utc)
        return date

    def date_to_local(self, date):
        """Convert a datetime to the observer's timezone.
        NOTE: If the datetime object is not timezone aware, it is
        assumed to be in UTC.
        """
        if date.tzinfo is not None:
            # date is timezone-aware
            date = date.astimezone(self.tz_local)

        else:
            # date is a naive date: assume expressed in UTC
            date = date.replace(tzinfo=self.tz_utc)
            # and converted to local time
            date = date.astimezone(self.tz_local)

        return date

    def set_date(self, date):
        """Set the date for the observer.  This is converted and
        stored internally in the timezone set for the observer.
        """
        self.date = self.date_to_local(date)
        # ephem deals only in UTC
        self.site.date = ephem.Date(self.date_to_utc(self.date))

    def radec_of(self, az_deg, alt_deg):
        ra, dec = self.site.radec_of(np.radians(az_deg), np.radians(alt_deg))
        ra_deg, dec_deg = np.degrees([ra, dec])
        return ra_deg, dec_deg

    def azalt_of(self, ra_deg, dec_deg):
        body = ephem.FixedBody()
        body._ra = np.radians(ra_deg)
        body._dec = np.radians(dec_deg)
        body.compute(self.site)

        az_deg, alt_deg = np.degrees([body.az, body.alt])
        return az_deg, alt_deg

    def calc(self, body, time_start):
        return body.calc(self, time_start)

    def get_date(self, date_str, timezone=None):
        """Get a datetime object, converted from a date string.
        The timezone is assumed to be that of the observer, unless
        explicitly supplied in the `timezone` kwarg.
        """
        if timezone is None:
            timezone = self.tz_local

        formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H',
                   '%Y-%m-%d']
        for fmt in formats:
            try:
                date = datetime.strptime(date_str, fmt)
                # Localize to the requested timezone
                date = date.replace(tzinfo=timezone)
                return date

            except ValueError as e:
                continue

        raise ValueError("Format must be one of: {}".str(formats))

    ## def _observable(self, target, time_start, time_stop,
    ##                el_min_deg, el_max_deg,
    ##                airmass=None):
    ##     c1 = self.calc(target, time_start)
    ##     c2 = self.calc(target, time_stop)

    ##     return ((el_min_deg <= c1.alt_deg <= el_max_deg) and
    ##             (el_min_deg <= c2.alt_deg <= el_max_deg)
    ##             and
    ##             ((airmass is None) or ((c1.airmass <= airmass) and
    ##                                    (c2.airmass <= airmass))))

    def observable(self, target, time_start, time_stop,
                   el_min_deg, el_max_deg, time_needed,
                   airmass=None, moon_sep=None):
        """
        Return True if `target` is observable between `time_start` and
        `time_stop`, defined by whether it is between elevation `el_min`
        and `el_max` during that period, and whether it meets the minimum
        airmass.
        """
        # set observer's horizon to elevation for el_min or to achieve
        # desired airmass
        if airmass != None:
            # compute desired altitude from airmass
            alt_deg = airmass2alt(airmass)
            min_alt_deg = max(alt_deg, el_min_deg)
        else:
            min_alt_deg = el_min_deg

        site = self.get_site(date=time_start, horizon_deg=min_alt_deg)

        d1 = self.calc(target, time_start)

        # TODO: worry about el_max_deg

        # important: ephem only deals with UTC!!
        time_start_utc = ephem.Date(self.date_to_utc(time_start))
        time_stop_utc = ephem.Date(self.date_to_utc(time_stop))
        #print("period (UT): %s to %s" % (time_start_utc, time_stop_utc))

        if d1.alt_deg >= min_alt_deg:
            # body is above desired altitude at start of period
            # so calculate next setting
            time_rise = time_start_utc
            time_set = site.next_setting(target.body._body,
                                         start=time_start_utc)
            #print("body already up: set=%s" % (time_set))

        else:
            # body is below desired altitude at start of period
            try:
                time_rise = site.next_rising(target.body._body,
                                             start=time_start_utc)
                time_set = site.next_setting(target.body._body,
                                             start=time_start_utc)
            except ephem.NeverUpError:
                return (False, None, None)

            #print("body not up: rise=%s set=%s" % (time_rise, time_set))
            ## if time_rise < time_set:
            ##     print("body still rising, below threshold")
            ##     # <-- body is still rising, just not high enough yet
            ## else:
            ##     # <-- body is setting
            ##     print("body setting, below threshold")
            ##     # calculate rise time backward from end of period
            ##     #time_rise = site.previous_rising(target.body, start=time_stop_utc)
            ##     pass

        if time_rise < time_start_utc:
            diff = time_rise - time_start_utc
            ## raise AssertionError("time rise (%s) < time start (%s)" % (
            ##         time_rise, time_start))
            print(("WARNING: time rise (%s) < time start (%s)" % (
                    time_rise, time_start)))
            time_rise = time_start_utc

        # last observable time is setting or end of period,
        # whichever comes first
        time_end = min(time_set, time_stop_utc)
        # calculate duration in seconds (subtracting two ephem Date
        # objects seems to give a fraction in days)
        duration = (time_end - time_rise) * 86400.0
        # object is observable as long as the duration that it is
        # up is as long or longer than the time needed
        diff = duration - float(time_needed)
        #can_obs = diff > -0.001
        can_obs = duration > time_needed
        #print("can_obs=%s duration=%f needed=%f diff=%f" % (
        #    can_obs, duration, time_needed, diff))

        # convert times back to datetime's
        time_rise = self.date_to_local(time_rise.datetime())
        time_end = self.date_to_local(time_end.datetime())

        return (can_obs, time_rise, time_end)

    def distance(self, tgt1, tgt2, time_start):
        c1 = self.calc(tgt1, time_start)
        c2 = self.calc(tgt2, time_start)

        d_alt = c1.alt_deg - c2.alt_deg
        d_az = c1.az_deg - c2.az_deg
        return (d_alt, d_az)

    def _set_site_date(self, date):
        if not isinstance(date, ephem.Date):
            if date is None:
                date = self.date
            date = self.date_to_utc(date)

            date = ephem.Date(date)
        self.site.date = date

    def sunset(self, date=None):
        """Returns sunset in observer's time."""
        self.site.horizon = self.horizon
        self._set_site_date(date)
        r_date = self.site.next_setting(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def sunrise(self, date=None):
        """Returns sunrise in observer's time."""
        self.site.horizon = self.horizon
        self._set_site_date(date)
        r_date = self.site.next_rising(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def evening_twilight_6(self, date=None):
        """Returns evening 6 degree civil twilight(civil dusk) in observer's time.
        """
        self.site.horizon = self.horizon6
        self._set_site_date(date)
        r_date = self.site.next_setting(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def evening_twilight_12(self, date=None):
        """Returns evening 12 degree (nautical) twilight in observer's time.
        """
        self.site.horizon = self.horizon12
        self._set_site_date(date)
        r_date = self.site.next_setting(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def evening_twilight_18(self, date=None):
        """Returns evening 18 degree (civil) twilight in observer's time.
        """
        self.site.horizon = self.horizon18
        self._set_site_date(date)
        r_date = self.site.next_setting(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def morning_twilight_6(self, date=None):
        """Returns morning 6 degree civil twilight(civil dawn) in observer's time.
        """
        self.site.horizon = self.horizon6
        self._set_site_date(date)
        r_date = self.site.next_rising(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def morning_twilight_12(self, date=None):
        """Returns morning 12 degree (nautical) twilight in observer's time.
        """
        self.site.horizon = self.horizon12
        self._set_site_date(date)
        r_date = self.site.next_rising(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def morning_twilight_18(self, date=None):
        """Returns morning 18 degree (civil) twilight in observer's time.
        """
        self.site.horizon = self.horizon18
        self._set_site_date(date)
        r_date = self.site.next_rising(self.sun)
        r_date = self.date_to_local(r_date.datetime())
        return r_date

    def sun_set_rise_times(self, date=None):
        """Sunset, sunrise and twilight times. Returns a tuple with
        (sunset, 12d, 18d, 18d, 12d, sunrise) in observer's time.
        """
        rstimes = (self.sunset(date=date),
                   self.evening_twilight_12(date=date),
                   self.evening_twilight_18(date=date),
                   self.morning_twilight_18(date=date),
                   self.morning_twilight_12(date=date),
                   self.sunrise(date=date))
        return rstimes

    def moon_rise(self, date=None):
        """Returns moon rise time in observer's time."""
        self._set_site_date(date)
        moonrise = self.site.next_rising(self.moon)
        moonrise = self.date_to_local(moonrise.datetime())
        ## if moonrise < self.sunset():
        ##     moonrise = None
        return moonrise

    def moon_set(self, date=None):
        """Returns moon set time in observer's time."""
        self._set_site_date(date)
        moonset = self.site.next_setting(self.moon)
        moonset = self.date_to_local(moonset.datetime())
        ## if moonset > self.sunrise():
        ##     moonset = None
        return moonset

    def moon_phase(self, date=None):
        """Returns moon percentage of illumination."""
        self._set_site_date(date)
        self.moon.compute(self.site)
        return self.moon.moon_phase

    def night_center(self, date=None):
        """Returns night center in observer's time."""
        sunset = self.sunset(date=date)
        sunrise = self.sunrise(date=sunset)
        center = sunset + timedelta(0, (sunrise - sunset).total_seconds() / 2.0)
        center = self.date_to_local(center)
        return center

    def get_text_almanac(self, date):
        date_s = date.strftime("%Y-%m-%d")
        text = ''
        text += 'Almanac for the night of %s\n' % date_s.split()[0]
        text += '\nEvening\n'
        text += '_'*30 + '\n'
        rst = self.sun_set_rise_times(date=date)
        rst = [t.strftime('%H:%M') for t in rst]
        text += 'Sunset: %s\n12d: %s\n18d: %s\n' % (rst[0], rst[1], rst[2])
        text += '\nMorning\n'
        text += '_'*30 + '\n'
        text += '18d: %s\n12d: %s\nSunrise: %s\n' % (rst[3], rst[4], rst[5])
        return text

    def get_target_info(self, target, time_start=None, time_stop=None,
                        time_interval=5):
        """Compute various values for a target from sunrise to sunset.
        """

        def _set_time(dtime):
            # Sets time to nice rounded value
            y, m ,d, hh, mm, ss = dtime.tuple()
            mm = mm - (mm % 5)
            return ephem.Date(datetime(y, m , d, hh, mm, 5, 0))

        def _set_data_range(time_start, time_stop, t_ival):
            # Returns numpy array of dates
            ss = _set_time(ephem.Date(ephem.Date(time_start) - t_ival))
            sr = _set_time(ephem.Date(ephem.Date(time_stop) + t_ival))
            return np.arange(ss, sr, t_ival)

        if time_start is None:
            # default for start time is sunset on the current date
            time_start = self.sunset()
        if time_stop is None:
            # default for stop time is sunrise on the current date
            time_stop = self.sunrise(date=time_start)

        t_range = _set_data_range(self.date_to_utc(time_start),
                                  self.date_to_utc(time_stop),
                                  time_interval * ephem.minute)
        #print('computing airmass history...')
        history = []

        # TODO: this should probably return a generator
        for ut in t_range:
            # ugh
            tup = ephem.Date(ut).tuple()
            args = tup[:-1] + (int(tup[-1]),)
            ut_with_tz = datetime(*args).replace(tzinfo=self.tz_utc)
            info = target.calc(self, ut_with_tz)
            history.append(info)
        #print(('computed airmass history', self.history))
        return history

    def get_target_info_table(self, target, time_start=None, time_stop=None):
        """Prints a table of hourly airmass data"""
        history = self.get_target_info(target, time_start=time_start,
                                       time_stop=time_stop)
        text = ''
        format = '%-16s  %-5s  %-5s  %-5s  %-5s  %-5s %-5s\n'
        header = ('Date       Local', 'UTC', 'LMST', 'HA', 'PA', 'AM', 'Moon')
        hstr = format % header
        text += hstr
        text += '_'*len(hstr) + '\n'
        for info in history:
            s_lt = info.lt.strftime('%d%b%Y  %H:%M')
            s_utc = info.ut.strftime('%H:%M')
            s_ha = ':'.join(str(ephem.hours(info.ha)).split(':')[:2])
            s_lmst = ':'.join(str(ephem.hours(info.lmst)).split(':')[:2])
            #s_pa = round(info.pang*180.0/np.pi, 1)
            s_pa = round(info.pang, 1)
            s_am = round(info.airmass, 2)
            s_ma = round(info.moon_alt, 1)
            if s_ma < 0:
                s_ma = ''
            s_data = format % (s_lt, s_utc, s_lmst, s_ha, s_pa, s_am, s_ma)
            text += s_data
        return text

    def __repr__(self):
        return self.name

    __str__ = __repr__


class Body(object):

    def __init__(self, name, ra, dec, equinox):
        super(Body, self).__init__()

        self.name = name
        self.ra = ra
        self.dec = dec
        self.equinox = equinox

        xeph_line = "%s,f|A,%s,%s,0.0,%s" % (name[:20], ra, dec, equinox)
        self._body = ephem.readdb(xeph_line)

    def calc(self, observer, date):
        return CalculationResult(self._body, observer, date)


class SSBody(object):

    def __init__(self, name, body):
        super(SSBody, self).__init__()

        self.name = name
        self._body = body

    def calc(self, observer, date):
        return CalculationResult(self._body, observer, date)


class CalculationResult(object):

    def __init__(self, body, observer, date):
        """
        `date` is a datetime.datetime object converted to observer's
        time.
        """
        self.site = observer.site
        self.body = body
        self.date = observer.date_to_local(date)
        self.date_utc = observer.date_to_utc(self.date)

        # Can/should this calculation be postponed?
        self.site.date = ephem.Date(self.date_utc)
        self.body.compute(self.site)

        self.lt = self.date
        self.ra = self.body.ra
        self.dec = self.body.dec
        self.alt = float(self.body.alt)
        self.az = float(self.body.az)
        # TODO: deprecate
        self.alt_deg = math.degrees(self.alt)
        self.az_deg = math.degrees(self.az)

        # properties
        self._ut = None
        self._gmst = None
        self._lmst = None
        self._ha = None
        self._pang = None
        self._am = None
        self._moon_alt = None
        self._moon_pct = None
        self._moon_sep = None


    @property
    def ut(self):
        if self._ut is None:
            self._ut = self.lt.astimezone(tz.UTC)
        return self._ut

    @property
    def gmst(self):
        if self._gmst is None:
            jd = self.julian_date(self.ut)
            T = (jd - 2451545.0)/36525.0
            gmstdeg = 280.46061837+(360.98564736629*(jd-2451545.0))+(0.000387933*T*T)-(T*T*T/38710000.0)
            self._gmst = ephem.degrees(gmstdeg*np.pi/180.0)
        return self._gmst

    @property
    def lmst(self):
        if self._lmst is None:
            lmst = ephem.degrees(self.gmst + self.site.long)
            self._lmst = lmst.norm
        return self._lmst

    @property
    def ha(self):
        if self._ha is None:
            self._ha = self.lmst - self.ra
        return self._ha

    @property
    def pang(self):
        if self._pang is None:
            self._pang = self.calc_parallactic(float(self.dec),
                                               float(self.ha),
                                               float(self.site.lat),
                                               self.az)
        return self._pang

    @property
    def airmass(self):
        if self._am is None:
            self._am = self.calc_airmass(self.alt)
        return self._am

    @property
    def moon_alt(self):
        if self._moon_alt is None:
            moon_alt, moon_pct, moon_sep = self.calc_moon(self.site, self.body)
            self._moon_alt = moon_alt
            self._moon_pct = moon_pct
            self._moon_sep = moon_sep
        return self._moon_alt

    @property
    def moon_pct(self):
        if self._moon_pct is None:
            moon_alt, moon_pct, moon_sep = self.calc_moon(self.site, self.body)
            self._moon_alt = moon_alt
            self._moon_pct = moon_pct
            self._moon_sep = moon_sep
        return self._moon_pct

    @property
    def moon_sep(self):
        if self._moon_sep is None:
            moon_alt, moon_pct, moon_sep = self.calc_moon(self.site, self.body)
            self._moon_alt = moon_alt
            self._moon_pct = moon_pct
            self._moon_sep = moon_sep
        return self._moon_sep

    def julian_date(self, val):
        # val = radec.julianDate(val.timetuple())
        val = ephem.julian_date(val)
        return val

    def calc_GMST(self, date):
        """Compute Greenwich Mean Sidereal Time"""
        jd = self.julian_date(date)
        T = (jd - 2451545.0)/36525.0
        gmstdeg = 280.46061837+(360.98564736629*(jd-2451545.0))+(0.000387933*T*T)-(T*T*T/38710000.0)
        gmst = ephem.degrees(gmstdeg*np.pi/180.0)
        return gmst

    def calc_LMST(self, date, longitude):
        """Compute Local Mean Sidereal Time"""
        gmst = self.calc_GMST(date)
        lmst = ephem.degrees(gmst + longitude)
        return lmst.norm

    def calc_HA(self, lmst, ra):
        """Compute Hour Angle"""
        return lmst - ra

    def calc_parallactic(self, dec, ha, lat, az):
        """Compute parallactic angle"""
        if np.cos(dec) != 0.0:
            sinp = -1.0*np.sin(az)*np.cos(lat)/np.cos(dec)
            cosp = -1.0*np.cos(az)*np.cos(ha)-np.sin(az)*np.sin(ha)*np.sin(lat)
            parang = ephem.degrees(np.arctan2(sinp, cosp))
        else:
            if lat > 0.0:
                parang = np.pi
            else:
                parang = 0.0
        return parang

    def calc_airmass(self, alt):
        """Compute airmass"""
        if alt < ephem.degrees('03:00:00'):
            alt = ephem.degrees('03:00:00')
        sz = 1.0/np.sin(alt) - 1.0
        xp = 1.0 + sz*(0.9981833 - sz*(0.002875 + 0.0008083*sz))
        return xp

    def calc_moon(self, site, body):
        """Compute Moon altitude"""
        site.date = ephem.Date(self.date_utc)
        moon = ephem.Moon(site)
        #moon.compute(site)
        moon_alt = math.degrees(float(moon.alt))
        # moon.phase is % of moon that is illuminated
        moon_pct = moon.moon_phase
        # calculate distance from target
        moon_sep = ephem.separation(moon, body)
        moon_sep = math.degrees(float(moon_sep))
        return (moon_alt, moon_pct, moon_sep)

    def calc_separation_alt_az(self, body):
        """Compute deltas for azimuth and altitude from another target"""
        self.body.compute(self.site)
        body.body.compute(self.site)

        delta_az = float(self.body.az) - float(target.az)
        delta_alt = float(self.body.alt) - float(target.alt)
        return (delta_alt, delta_az)


Moon = SSBody('Moon', ephem.Moon())
Sun = SSBody('Sun', ephem.Sun())
Mercury = SSBody('Mercury', ephem.Mercury())
Venus = SSBody('Venus', ephem.Venus())
Mars = SSBody('Mars', ephem.Mars())
Jupiter = SSBody('Jupiter', ephem.Jupiter())
Saturn = SSBody('Saturn', ephem.Saturn())
Uranus = SSBody('Uranus', ephem.Uranus())
Neptune = SSBody('Neptune', ephem.Neptune())
Pluto = SSBody('Pluto', ephem.Pluto())


#END
