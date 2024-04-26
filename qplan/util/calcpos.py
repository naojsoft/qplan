#
# calcpos.py -- module for wrapping astronomical ephemeris calculations
#

# third-party imports
import numpy as np
from datetime import datetime, time, timedelta
from dateutil import tz
import dateutil.parser
import copy

import erfa
from astropy.coordinates import SkyCoord, Latitude, Longitude
from astropy.time import Time
from astropy import units as u

from skyfield.api import Star, load, wgs84
from skyfield.earthlib import refraction
from skyfield import almanac
# Constants

earth_radius_m = 6378136.6
solar_radius_deg = 0.25
moon_radius_deg = 0.26

ssbodies = load('de421.bsp')
timescale = load.timescale()

# used for twilight calculations
horizon_6 = -6.0
horizon_12 = -12.0
horizon_18 = -18.0


def alt2airmass(alt_deg):
    xp = 1.0 / np.sin(np.radians(alt_deg + 244.0/(165.0 + 47*alt_deg**1.1)))
    return xp

am_inv = np.array([(alt2airmass(alt), alt) for alt in range(0, 91, 1)])

def airmass2alt(am):
    # TODO: vectorize
    if am < am_inv.T[0][-1]:
        return 90.0
    i = np.argmax(am_inv.T[0] < am)
    i = np.clip(i - 1, 0, len(am_inv) - 1)
    return am_inv.T[1][i]

#### Classes ####


class Observer(object):
    """
    Observer
    """
    def __init__(self, name, timezone=None, longitude=None, latitude=None,
                 elevation=0, pressure=0, temperature=0, humidity=0,
                 date=None, wavelength=None, description=None):
        super(Observer, self).__init__()
        self.name = name
        if timezone is None:
            # default to UTC
            timezone = tz.UTC
        self.tz_local = timezone
        if isinstance(longitude, str):
            self.lon_deg = Longitude(longitude, unit=u.deg).deg
        else:
            self.lon_deg = longitude
        if isinstance(latitude, str):
            self.lat_deg = Latitude(latitude, unit=u.deg).deg
        else:
            self.lat_deg = latitude
        self.elev_m = elevation
        self.pressure_mbar = pressure
        self.temp_C = temperature
        self.rh_pct = humidity / 100.
        if date is None:
            date = datetime.now(tz=self.tz_local)
        self.date = date
        self.wavelength = wavelength
        self.description = description
        #self.horizon = -1 * np.sqrt(2 * elevation / earth_radius_m)
        self.horizon = np.degrees(- np.arccos(earth_radius_m / (earth_radius_m + self.elev_m)))

        earth = ssbodies['earth']
        self.location = earth + wgs84.latlon(latitude_degrees=self.lat_deg,
                                             longitude_degrees=self.lon_deg,
                                             elevation_m=self.elev_m)

    @property
    def timezone(self):
        return self.tz_local

    @property
    def tz_utc(self):
        return tz.UTC

    def date_to_utc(self, date):
        """Convert a datetime to UTC.
        NOTE: If the datetime object is not timezone aware, it is
        assumed to be in the timezone of the observer.
        """
        if date.tzinfo is not None:
            # date is timezone-aware
            date = date.astimezone(tz.UTC)

        else:
            # date is a naive date: assume expressed in local time
            date = date.replace(tzinfo=self.tz_local)
            # and converted to UTC
            date = date.astimezone(tz.UTC)
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
            date = date.replace(tzinfo=tz.UTC)
            # and converted to local time
            date = date.astimezone(self.tz_local)

        return date

    def set_date(self, date):
        """Set the date for the observer.  This is converted and
        stored internally in the timezone set for the observer.
        """
        self.date = self.date_to_local(date)

    def radec_of(self, az_deg, alt_deg, date=None):
        if date is None:
            date = self.date
        obstime = timescale.from_datetime(date)
        apparent = self.location.at(obstime).from_altaz(alt_degrees=alt_deg,
                                                        az_degrees=az_deg)
        ra, dec, distance = apparent.radec()
        ra_deg, dec_deg = ra.degrees, dec.degrees
        return ra_deg, dec_deg

    def azalt_of(self, ra_deg, dec_deg, date=None):
        if date is None:
            date = self.date
        coord = Star(ra_hours = ra_deg / 15.0, dec_degrees=dec_deg)
        obstime = timescale.from_datetime(date)
        astrometric = self.location.at(obstime).observe(coord)
        apparent = astrometric.apparent()
        alt, az, distance = apparent.altaz(temperature_C=self.temp_C,
                                           pressure_mbar=self.pressure_mbar)
        az_deg, alt_deg = az.degrees, alt.degrees
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

        if isinstance(date_str, datetime):
            # user actually passed a datetime object
            dt = date_str
        else:
            dt = dateutil.parser.parse(date_str)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone)
        else:
            dt = dt.astimezone(timezone)
        return dt

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

        # TODO: worry about el_max_deg

        coord = target._get_coord()
        obstime = timescale.from_datetime(time_start)
        astrometric = self.location.at(obstime).observe(coord)
        apparent = astrometric.apparent()
        alt, az, distance = apparent.altaz(temperature_C=self.temp_C,
                                           pressure_mbar=self.pressure_mbar)
        alt_deg = alt.degrees

        if alt_deg >= min_alt_deg:
            # body is above desired altitude at start of period
            # so calculate next setting
            time_rise = time_start_utc
            _t_set = self._find_setting(coord, time_start, time_end,
                                        min_alt_deg)
            time_set = _t_set.astimezone(self.tz_local)
            #print("body already up: set=%s" % (time_set))

        else:
            # body is below desired altitude at start of period
            _t_rise = self._find_rising(coord, time_start,
                                        time_end, min_alt_deg)
            time_rise = _t_rise.astimezone(self.tz_local)
            _t_set = self._find_setting(coord, time_start_utc,
                                        time_end_utc, min_alt_deg)
            time_set = _t_set.astimezone(self.tz_local)

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

        if time_rise < time_start:
            diff = time_rise - time_start
            ## raise AssertionError("time rise (%s) < time start (%s)" % (
            ##         time_rise, time_start))
            print(("WARNING: time rise (%s) < time start (%s)" % (
                    time_rise, time_start)))
            time_rise = time_start

        # last observable time is setting or end of period,
        # whichever comes first
        time_end = min(time_set, time_stop)
        # calculate duration in seconds (subtracting two datetime objects)
        duration = (time_end - time_rise).total_seconds()
        # object is observable as long as the duration that it is
        # up is as long or longer than the time needed
        diff = duration - float(time_needed)
        #can_obs = diff > -0.001
        can_obs = duration > time_needed
        #print("can_obs=%s duration=%f needed=%f diff=%f" % (
        #    can_obs, duration, time_needed, diff))

        return (can_obs, time_rise, time_end)

    def distance(self, tgt1, tgt2, time_start):
        c1 = self.calc(tgt1, time_start)
        c2 = self.calc(tgt2, time_start)

        d_alt = c1.alt_deg - c2.alt_deg
        d_az = c1.az_deg - c2.az_deg
        return (d_alt, d_az)

    def _find_setting(self, coord, start_dt, stop_dt, horizon_deg):
        t0 = timescale.from_datetime(start_dt)
        t1 = timescale.from_datetime(stop_dt)
        # TODO: refraction function does not appear to work as expected
        #r = refraction(horizon_deg, temperature_C=self.temp_C,
        #               pressure_mbar=self.pressure_mbar)
        r = horizon_deg
        t, y = almanac.find_settings(self.location, coord, t0, t1,
                                     horizon_degrees=r)
        return t, y

    def _find_rising(self, coord, start_dt, stop_dt, horizon_deg):
        t0 = timescale.from_datetime(start_dt)
        t1 = timescale.from_datetime(stop_dt)
        # TODO: refraction function does not appear to work as expected
        #r = refraction(horizon_deg, temperature_C=self.temp_C,
        #               pressure_mbar=self.pressure_mbar)
        r = horizon_deg
        t, y = almanac.find_risings(self.location, coord, t0, t1,
                                    horizon_degrees=r)
        return t, y

    def get_last(self, date=None):
        """Return the local apparent sidereal time."""
        # TODO: use skyfield to calculate this (see CalculationResult "last")
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)
        last = Time(date).sidereal_time('apparent',
                                        longitude=self.lon_deg * u.deg)
        time_s = str(last).replace('h', ':').replace('m', ':').replace('s', '')
        dt = dateutil.parser.parse(time_s)
        return time(hour=dt.hour, minute=dt.minute, second=dt.second,
                    microsecond=dt.microsecond)

    def sunset(self, date=None):
        """Returns sunset in observer's time."""
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_setting(ssbodies['sun'], date,
                                  date + timedelta(days=1, hours=0),
                                  self.horizon - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def sunrise(self, date=None):
        """Returns sunrise in observer's time."""
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_rising(ssbodies['sun'], date,
                                 date + timedelta(days=1, hours=0),
                                 self.horizon - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def evening_twilight_6(self, date=None):
        """Returns evening 6 degree civil twilight(civil dusk) in observer's time.
        """
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_setting(ssbodies['sun'], date,
                                  date + timedelta(days=1, hours=0),
                                  horizon_6 - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def evening_twilight_12(self, date=None):
        """Returns evening 12 degree (nautical) twilight in observer's time.
        """
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_setting(ssbodies['sun'], date,
                                  date + timedelta(days=1, hours=0),
                                  horizon_12 - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def evening_twilight_18(self, date=None):
        """Returns evening 18 degree (civil) twilight in observer's time.
        """
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_setting(ssbodies['sun'], date,
                                  date + timedelta(days=1, hours=0),
                                  horizon_18 - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def morning_twilight_6(self, date=None):
        """Returns morning 6 degree civil twilight(civil dawn) in observer's time.
        """
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_rising(ssbodies['sun'], date,
                                 date + timedelta(days=1, hours=0),
                                 horizon_6) # - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def morning_twilight_12(self, date=None):
        """Returns morning 12 degree (nautical) twilight in observer's time.
        """
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_rising(ssbodies['sun'], date,
                                 date + timedelta(days=1, hours=0),
                                 horizon_12) # - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def morning_twilight_18(self, date=None):
        """Returns morning 18 degree (civil) twilight in observer's time.
        """
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_rising(ssbodies['sun'], date,
                                 date + timedelta(days=1, hours=0),
                                 horizon_18) # - solar_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

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
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_rising(ssbodies['moon'], date,
                                 date + timedelta(days=1, hours=0),
                                 self.horizon - moon_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def moon_set(self, date=None):
        """Returns moon set time in observer's time."""
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        t, y = self._find_setting(ssbodies['sun'], date,
                                  date + timedelta(days=1, hours=0),
                                  self.horizon - moon_radius_deg * 2)
        return t[0].astimezone(self.tz_local)

    def moon_illumination(self, date=None):
        """Returns moon percentage of illumination."""
        if date is None:
            date = self.date
        else:
            date = self.get_date(date)

        cres = Moon.calc(self, date)
        return cres.moon_pct

    # TO BE DEPRECATED
    moon_phase = moon_illumination

    def night_center(self, date=None):
        """Returns night center in observer's time."""
        sunset = self.sunset(date=date)
        sunrise = self.sunrise(date=date)
        center = sunset + timedelta(seconds=(sunrise - sunset).total_seconds() / 2.0)
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

        if time_start is None:
            # default for start time is sunset on the current date
            time_start = self.sunset()
        if time_stop is None:
            # default for stop time is sunrise on the current date
            time_stop = self.sunrise(date=time_start)

        # create date array
        dts = []
        time_t = self.date_to_utc(time_start)
        time_e = self.date_to_utc(time_stop)
        while time_t < time_e:
            dts.append(time_t)
            time_t = time_t + timedelta(minutes=time_interval)
        dt_arr = np.array(dts)

        # TODO: return vector calc object
        # return target.calc(self, dt_arr)
        res = [target.calc(self, dt) for dt in dt_arr]
        return res

    def get_target_info_table(self, target, time_start=None, time_stop=None):
        """Prints a table of hourly airmass data"""
        history = self.get_target_info(target, time_start=time_start,
                                    time_stop=time_stop)
        text = ''
        format = '%-16s  %-5s  %-5s  %-5s  %-5s  %-5s %-5s\n'
        header = ('Date       Local', 'UTC', 'LMST', 'HA', 'PA', 'AM', 'Moon')
        hstr = format % header
        text += hstr
        text += '_' * len(hstr) + '\n'
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

    def _get_coord(self):   #noqa
        # vector construction, if the value passed is an array
        if isinstance(self.ra, np.ndarray):
            if isinstance(self.ra[0], str):
                # assume units are in hours and parse with astropy
                coord = SkyCoord(self.ra, self.dec,
                                 unit=(u.hourangle, u.degree))
                ra_deg, dec_deg = coord.ra.degree, coord.dec.degree
            else:
                ra_deg, dec_deg = self.ra.astype(float), self.dec.astype(float)

            #epoch = np.tile(np.array([2000.0]), len(ra_deg) - 1)
            epoch = np.array([2000.0] * len(ra_deg))
            import pandas as pd
            df = pd.DataFrame(dict(names=self.name, ra_degrees=ra_deg,
                                   ra_hours=ra_deg / 15.0,
                                   dec_degrees=dec_deg,
                                   epoch_year=epoch))
            coord = Star.from_dataframe(df)
        else:
            if isinstance(self.ra, str):
                # assume units are in hours and parse with astropy
                coord = SkyCoord(self.ra, self.dec,
                                 unit=(u.hourangle, u.degree))
                ra_deg, dec_deg = coord.ra.degree, coord.dec.degree
            else:
                ra_deg, dec_deg = float(self.ra), float(self.dec)
            coord = Star(ra_hours = ra_deg / 15.0, dec_degrees=dec_deg)

        return coord

    def calc(self, observer, date):
        return CalculationResult(self, observer, date)


class SSBody(object):

    def __init__(self, name, body):
        super(SSBody, self).__init__()

        self.name = name
        self._body = body

    def _get_coord(self):
        return self._body

    def calc(self, observer, date):
        return CalculationResult(self, observer, date)


class CalculationResult(object):

    def __init__(self, body, observer, date):
        """
        `date` is a datetime.datetime object converted to observer's
        time.
        """
        self.observer = observer
        self.body = body
        # self.date = observer.date_to_local(date)
        # self.date_utc = observer.date_to_utc(self.date)
        # vector construction, if the value passed is an array
        if isinstance(date, np.ndarray):
            self.obstime = timescale.from_datetimes(date)
        else:
            self.obstime = timescale.from_datetime(date)

        self.will_be_visible = True
        # properties
        self._ut = None
        self._lt = None
        self._jd = None
        self._mjd = None
        self._gmst = None
        self._gast = None
        self._lmst = None
        self._last = None
        self._ra = None
        self._dec = None
        self._alt = None
        self._az = None
        self._ha = None
        self._pang = None
        self._am = None
        self._moon_alt = None
        self._moon_pct = None
        self._moon_sep = None
        self._atmos_disp = None

        # Conversion factor for wavelengths (Angstrom -> micrometer)
        self.angstrom_to_mm = 1. / 10000.

    @property
    def name(self):
        return self.body.name

    @property
    def ra(self):
        """Return right ascension in radians."""
        if self._ra is None:
            self._calc_radec()
        return self._ra.radians

    @property
    def ra_deg(self):
        """Return right ascension in degrees."""
        return np.degrees(self.ra)

    @property
    def dec(self):
        """Return declination in radians."""
        if self._dec is None:
            self._calc_radec()
        return self._dec.radians

    @property
    def dec_deg(self):
        """Return declination in degrees."""
        return np.degrees(self.dec)

    @property
    def equinox(self):
        return self.body.equinox

    @property
    def alt(self):
        """Return altitude in radians."""
        if self._alt is None:
            self._calc_altaz()
        return self._alt.radians

    @property
    def az(self):
        """Return azimuth in radians."""
        if self._az is None:
            self._calc_altaz()
        return self._az.radians

    @property
    def alt_deg(self):
        """Return altitude in degrees."""
        if self._az is None:
            self._calc_altaz()
        return self._alt.degrees

    @property
    def az_deg(self):
        """Return azimuth in degrees."""
        if self._az is None:
            self._calc_altaz()
        return self._az.degrees

    @property
    def lt(self):
        """Return local time as a Python timzezone-aware datetime."""
        if self._lt is None:
            self._lt = self.obstime.astimezone(self.observer.tz_local)
        return self._lt

    @property
    def ut(self):
        """Return universal time as a Python timzezone-aware datetime."""
        if self._ut is None:
            self._ut = self.obstime.utc_datetime()
        return self._ut

    @property
    def jd(self):
        """Return the Julian Date."""
        if self._jd is None:
            self._jd = self.obstime.ut1
        return self._jd

    @property
    def mjd(self):
        """Return the Mean Julian Date."""
        if self._mjd is None:
            self._mjd = self.jd - 2400000.5
        return self._mjd

    @property
    def gmst(self):
        """Return Greenwich Mean Sidereal Time in radians."""
        if self._gmst is None:
            # NOTE:obstime.gmst is in hours
            self._gmst = np.radians(self.obstime.gmst * 15.0)
        return self._gmst

    @property
    def gast(self):
        """Return Greenwich Apparent Sidereal Time in radians."""
        if self._gast is None:
            # NOTE:obstime.gast is in hours
            self._gast = np.radians(self.obstime.gast * 15.0)
        return self._gast

    @property
    def lmst(self):
        """Return Local Mean Sidereal Time in radians."""
        if self._lmst is None:
            self._lmst = self.gmst + \
                np.radians(np.fmod(self.observer.lon_deg + 360., 360.))
        return self._lmst

    @property
    def last(self):
        """Return Local Apparent Sidereal Time in radians."""
        if self._last is None:
            self._last = self.gast + \
                np.radians(np.fmod(self.observer.lon_deg + 360., 360.))
        return self._last

    @property
    def ha(self):
        """Return the Hour Angle in radians."""
        if self._ha is None:
            self._ha = self.lmst - self.ra
        return self._ha

    @property
    def pang(self):
        """Return the parallactic angle of the target(s) in radians."""
        if self._pang is None:
            self._pang = self._calc_parallactic(self.dec,
                                                self.ha,
                                                self.observer.lat_deg,
                                                self.az)
        return self._pang

    @property
    def pang_deg(self):
        """Return the parallactic angle of the target(s) in degrees."""
        return np.degrees(self.pang)

    @property
    def airmass(self):
        """Return the airmass of the target(s)."""
        if self._am is None:
            self._am = self._calc_airmass(self.alt_deg)
        return self._am

    @property
    def moon_alt(self):
        """Return the moon's altitude at the time of observation (in degrees)."""
        if self._moon_alt is None:
            # calculate moon altitude
            moon = ssbodies['moon']
            astrometric = self.observer.location.at(self.obstime).observe(moon)
            apparent = astrometric.apparent()
            alt, az, distance = apparent.altaz(temperature_C=self.observer.temp_C,
                                               pressure_mbar=self.observer.pressure_mbar)
            self._moon_alt = alt.degrees
        return self._moon_alt

    @property
    def moon_pct(self):
        """Return the moon's percentage of illumination (range: 0-1)."""
        if self._moon_pct is None:
            e = self.observer.location.at(self.obstime)
            s = e.observe(ssbodies['sun']).apparent()
            m = e.observe(ssbodies['moon']).apparent()
            self._moon_pct = m.fraction_illuminated(ssbodies['sun'])
        return self._moon_pct

    @property
    def moon_sep(self):
        """Return the moon's separation from target(s) (in degrees)."""
        if self._moon_sep is None:
            self._calc_altaz()
        return self._moon_sep

    @property
    def atmos_disp(self):
        if self._atmos_disp is None:
            self._atmos_disp = self._calc_atmos_disp(self.observer)
        return self._atmos_disp

    def _calc_parallactic(self, dec, ha, lat_deg, az):
        """Compute parallactic angle(s)."""
        lat = np.radians(lat_deg)
        cos_dec = np.cos(dec)
        if isinstance(cos_dec, np.ndarray):
            # handle poles (cos_dec == 0) in vector form
            # holds the result
            pang_res = np.zeros((len(dec)), float)
            pole = np.isclose(cos_dec, 0.0)
            notpole = np.logical_not(pole)

            sinp = -1.0 * np.sin(az[notpole]) * np.cos(lat) / cos_dec[notpole]
            cosp = -1.0 * np.cos(az[notpole]) * np.cos(ha[notpole]) - \
                              np.sin(az[notpole]) * np.sin(ha[notpole]) * np.sin(lat)
            pang_res[notpole] = np.arctan2(sinp[notpole], cosp[notpole])
            if lat > 0.0:
                pang_res[pole] = np.pi
            else:
                pang_res[pole] = 0.
        else:
            # scalar calculation
            if not np.isclose(cos_dec, 0.0):
                sinp = -1.0 * np.sin(az) * np.cos(lat) / cos_dec
                cosp = -1.0 * np.cos(az) * np.cos(ha) - \
                                  np.sin(az) * np.sin(ha) * np.sin(lat)
                pang_res = np.arctan2(sinp, cosp)
            else:
                if lat > 0.0:
                    pang_res = np.pi
                else:
                    parang = 0.
        return pang_res

    def _calc_airmass(self, alt_deg):
        """Compute airmass(es)"""
        alt_deg = np.clip(alt_deg, 3.0, None)
        sz = 1.0 / np.sin(np.radians(alt_deg)) - 1.0
        xp = 1.0 + sz*(0.9981833 - sz*(0.002875 + 0.0008083*sz))
        return xp

    def calc_separation_alt_az(self, body):
        """Compute deltas for azimuth and altitude from another target"""
        cr1 = self.body.calc(self.observer, self.ut)
        cr2 = body.calc(self.observer, self.ut)

        delta_az = cr1.az_deg - cr2.az_deg
        delta_alt = cr1.alt_deg - cr2.alt_deg
        return (delta_alt, delta_az)

    def _calc_atmos_refco(self, bar_press_mbar, temp_degc, rh_pct, wl_mm):
        """Compute atmospheric refraction coefficients (radians)"""
        refa, refb = erfa.refco(bar_press_mbar, temp_degc, rh_pct, wl_mm)
        return (refa, refb)

    def _calc_atmos_disp(self, observer):
        """Compute atmospheric dispersion (radians)"""
        bar_press_mbar = observer.pressure_mbar
        temp_degc = observer.temp_C
        rh_pct = observer.rh_pct
        wl = observer.wavelength
        zd_rad = np.subtract(np.pi / 2.0, self.alt)
        tzd = np.tan(zd_rad)
        if wl is None:
            raise ValueError('Wavelength is None')
        else:
            if isinstance(wl, dict):
                atmos_disp_rad = {}
                for k, w in wl.items():
                    wl_mm = w * self.angstrom_to_mm
                    refa, refb = self._calc_atmos_refco(bar_press_mbar, temp_degc, rh_pct, wl_mm)
                    atmos_disp_rad[k] = (refa + refb * tzd * tzd) * tzd
            elif isinstance(wl, list):
                atmos_disp_rad = []
                for w in wl:
                    wl_mm = w * self.angstrom_to_mm
                    refa, refb = self._calc_atmos_refco(bar_press_mbar, temp_degc, rh_pct, wl_mm)
                    atmos_disp_rad.append((refa + refb * tzd * tzd) * tzd)
            else:
                wl_mm = wl * self.angstrom_to_mm
                refa, refb = self._calc_atmos_refco(bar_press_mbar, temp_degc, rh_pct, wl_mm)
                atmos_disp_rad  = (refa + refb * tzd * tzd) * tzd
            return atmos_disp_rad

    def _calc_radec(self):
        coord = self.body._get_coord()
        if hasattr(coord, 'ra'):
            self._ra, self._dec = coord.ra, coord.dec
            self._ra_deg, self._dec_deg = coord.ra.hours * 15.0, coord.dec.degrees
        else:
            # moons, planets, etc.
            # Need to calculate the apparent ra/dec from the azalt
            self._calc_altaz()
            apparent = self.observer.location.at(self.obstime).from_altaz(alt_degrees=self.alt_deg,
                                                                          az_degrees=self.az_deg)
            self._ra, self._dec, distance = apparent.radec()
            self._ra_deg, self._dec_deg = self._ra.hours * 15.0, self._dec.degrees

    def _calc_altaz(self):
        coord = self.body._get_coord()
        astrometric = self.observer.location.at(self.obstime).observe(coord)
        apparent = astrometric.apparent()
        alt, az, distance = apparent.altaz(temperature_C=self.observer.temp_C,
                                           pressure_mbar=self.observer.pressure_mbar)
        self._az, self._alt = az, alt

        # get hour angle
        #self._ha, _dec, _dist = apparent.hadec()

        # calculate moon separation from target(s)
        # TODO: don't we need to specify a time here somehow?
        moon = ssbodies['moon']
        astrometric_m = self.observer.location.at(self.obstime).observe(moon)
        apparent_m = astrometric_m.apparent()
        sep = apparent.separation_from(apparent_m)
        self._moon_sep = sep.degrees

    def get_dict(self, columns=None):
        if columns is None:
            return dict(name=self.name, ra=self.ra, ra_deg=self.ra_deg,
                        dec=self.dec, dec_deg=self.dec_deg, az=self.az,
                        az_deg=self.az_deg, alt=self.alt, alt_deg=self.alt_deg,
                        lt=self.lt, ut=self.ut, jd=self.jd, mjd=self.mjd,
                        gast=self.gast, gmst=self.gmst, last=self.last,
                        lmst=self.lmst, ha=self.ha, pang=self.pang,
                        pang_deg=self.pang_deg, airmass=self.airmass,
                        moon_alt=self.moon_alt, moon_pct=self.moon_pct,
                        moon_sep=self.moon_sep,
                        atmos_disp_observing=self.atmos_disp['observing'],
                        atmos_disp_guiding=self.atmos_disp['guiding'])
        else:
            return {colname: getattr(self, colname) for colname in columns}


Moon = SSBody('Moon', ssbodies['moon'])
Sun = SSBody('Sun', ssbodies['sun'])
Mercury = SSBody('Mercury', ssbodies['mercury'])
Venus = SSBody('Venus', ssbodies['venus'])
Mars = SSBody('Mars', ssbodies['mars'])
Jupiter = SSBody('Jupiter', ssbodies['jupiter barycenter'])
Saturn = SSBody('Saturn', ssbodies['saturn barycenter'])
Uranus = SSBody('Uranus', ssbodies['uranus barycenter'])
Neptune = SSBody('Neptune', ssbodies['neptune barycenter'])
Pluto = SSBody('Pluto', ssbodies['pluto barycenter'])


#END
