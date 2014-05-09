#
# entity.py -- various entities used by queue system
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import tzinfo, timedelta, datetime

# local imports
import misc

# 3rd party imports
import ephem
import pytz
import numpy
import math

from ginga.misc import Bunch


class Program(object):
    """
    Program
    Defines a program that has been accepted for observation.
    """
    def __init__(self, proposal, rank=1.0, pi=None, observers=None,
                 propid=None, description=None):
        self.proposal = proposal
        if propid == None:
            # TODO: supposedly there is an algorithm to turn proposals
            # into propids
            propid = proposal
        self.propid = propid
        self.rank = rank
        # TODO: eventually this will contain all the relevant info
        # pertaining to a proposal
        
    def __repr__(self):
        return self.proposal

    __str__ = __repr__


class SlotError(Exception):
    pass

class Slot(object):
    """
    Slot -- a period of the night that can be scheduled.
    Defined by a start time and a duration in seconds.
    """
    
    def __init__(self, start_time, slot_len_sec, data=None):
        self.start_time = start_time
        self.stop_time = start_time + timedelta(0, slot_len_sec)
        self.data = data

    def split(self, start_time, slot_len_sec):
        """
        Split a slot into three slots.
        Parameters
        ----------
          start_time : a datetime compatible datetime object
              The time at which to split the slot
          slot_len_sec : int
              The length of the slot being inserted

        Returns
        -------
          A list of Slots formed by splitting the current slot.
          Depending on the overlap, there will be 1, 2 or 3 slots in the
          return list.
        """
        if start_time < self.start_time:
            raise SlotError("Start time (%s) < slot start time (%s)" % (
                start_time, self.start_time))

        stop_time = start_time + timedelta(0, slot_len_sec)
        if stop_time > self.stop_time:
            raise SlotError("Stop time (%s) > slot stop time (%s)" % (
                stop_time, self.stop_time))

        # define before slot
        slot_b = None
        if start_time > self.start_time:
            diff_sec = (start_time - self.start_time).total_seconds()
            slot_b = Slot(self.start_time, diff_sec, data=self.data)

        # define new displacing slot
        slot_c = Slot(start_time, slot_len_sec, data=self.data)

        # define after slot
        slot_d = None
        if stop_time < self.stop_time:
            diff_sec = (self.stop_time - stop_time).total_seconds()
            slot_d = Slot(stop_time, diff_sec, data=self.data)
            
        return (slot_b, slot_c, slot_d)

    def size(self):
        """
        Returns the length of the slot in seconds.
        """
        diff_sec = (self.stop_time - self.start_time).total_seconds()
        return diff_sec
    
    def __repr__(self):
        #s = self.start_time.strftime("%H:%M:%S")
        duration = self.size() / 60.0
        s = self.start_time.strftime("%H:%M") + ("(%.2fm)" % duration)
        return s

    __str__ = __repr__


class OB(object):
    """
    Observing Block
    Defines an item that can be scheduled during the night.
    
    """
    count = 1
    
    def __init__(self, program=None, target=None, telcfg=None,
                 inscfg=None, envcfg=None, total_time=None):
        self.id = "ob%04d" % (OB.count)
        OB.count += 1
        
        self.program = program

        # constraints
        self.target = target
        self.inscfg = inscfg
        self.telcfg = telcfg
        self.envcfg = envcfg
        self.total_time = total_time

    def __repr__(self):
        return self.id

    __str__ = __repr__


class BaseTarget(object):
    pass
    
class StaticTarget(object):
    def __init__(self, name, ra, dec, equinox=2000.0):
        self.name = name
        self.ra = ra
        self.dec = dec
        self.equinox = equinox

        xeph_line = "%s,f|A,%s,%s,0.0,%s" % (name[:20], ra, dec, equinox)
        self.body = ephem.readdb(xeph_line)
    
    def calc_GMST(self, date):
        """Compute Greenwich Mean Sidereal Time"""
        jd = ephem.julian_date(date)
        T = (jd - 2451545.0)/36525.0
        gmstdeg = 280.46061837+(360.98564736629*(jd-2451545.0))+(0.000387933*T*T)-(T*T*T/38710000.0)
        gmst = ephem.degrees(gmstdeg*numpy.pi/180.0)
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
        if numpy.cos(dec) != 0.0:
            sinp = -1.0*numpy.sin(az)*numpy.cos(lat)/numpy.cos(dec)
            cosp = -1.0*numpy.cos(az)*numpy.cos(ha)-numpy.sin(az)*numpy.sin(ha)*numpy.sin(lat)
            parang = ephem.degrees(numpy.arctan2(sinp, cosp))
        else:
            if lat > 0.0:
                parang = numpy.pi
            else:
                parang = 0.0
        return parang

    def calc_airmass(self, alt):
        """Compute airmass"""
        if alt < ephem.degrees('03:00:00'):
            alt = ephem.degrees('03:00:00')
        sz = 1.0/numpy.sin(alt) - 1.0
        xp = 1.0 + sz*(0.9981833 - sz*(0.002875 + 0.0008083*sz))
        return xp
    
    def calc_moon_alt(self, site):
        """Compute Moon altitude"""
        moon = ephem.Moon()
        moon.compute(site)
        return moon.alt
        
    def calc(self, observer, time_start):
        observer.set_date(time_start)
        self.body.compute(observer.site)
        
        ut = time_start.astimezone(pytz.utc)
        lst = self.calc_LMST(ut, observer.site.long)
        ha = self.calc_HA(lst, self.body.ra)
        alt = float(self.body.alt)
        az = float(self.body.az)
        pang = self.calc_parallactic(float(self.body.dec), float(ha),
                                     float(observer.site.lat),
                                     az)
        amass = self.calc_airmass(alt)
        moon_alt = self.calc_moon_alt(observer.site)

        res = Bunch.Bunch(ut=ut, lt=time_start, lst=lst, ha=ha,
                          pang=pang, airmass=amass, moon_alt=moon_alt,
                          alt=alt, az=az, alt_deg=math.degrees(alt),
                          az_deg=math.degrees(az))
        return res
    

class Observer(object):
    """
    Observer
    """
    def __init__(self, name, timezone=None, longitude=None, latitude=None,
                 elevation=None, pressure=None, temperature=None,
                 date=None, description=None):
        self.name = name
        self.timezone = timezone
        self.longitude = longitude
        self.latitude = latitude
        self.elevation = elevation
        self.pressure = pressure
        self.temperature = temperature
        self.date = date
        self.horizon = -1 * numpy.sqrt(2 * elevation / ephem.earth_radius)

        self.site = self.get_site(date=date)

    def get_site(self, date=None, horizon=None):
        site = ephem.Observer()
        site.lon = self.longitude
        site.lat = self.latitude
        site.elevation = self.elevation
        site.pressure = self.pressure
        site.temp = self.temperature
        if horizon != None:
            site.horizon = ephem.degrees(horizon)
        else:
            site.horizon = self.horizon
        site.epoch = 2000.0
        if date == None:
            now = datetime.now()
            date = self.get_date(now.strftime("%Y-%m-%d %H:%M:%S"))
        site.date = ephem.Date(date.astimezone(pytz.timezone('UTC')))
        return site
        
    def set_date(self, date):
        self.site.date = ephem.Date(date.astimezone(pytz.timezone('UTC')))
        
    def calc(self, body, time_start):
        return body.calc(self, time_start)
    
    def get_date(self, date_str, timezone=None):
        if timezone == None:
            timezone = self.timezone

        formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H',
                   '%Y-%m-%d']
        for fmt in formats:
            try:
                date = datetime.strptime(date_str, fmt)
                timetup = tuple(date.timetuple()[:6])
                # re-express as timezone
                date = datetime(*timetup, tzinfo=timezone)
                return date

            except ValueError as e:
                continue

        raise e

    def _observable(self, target, time_start, time_stop,
                   el_min_deg, el_max_deg,
                   airmass=None):
        c1 = self.calc(target, time_start)
        c2 = self.calc(target, time_stop)

        return ((el_min_deg <= c1.alt_deg <= el_max_deg) and
                (el_min_deg <= c2.alt_deg <= el_max_deg)
                and
                ((airmass == None) or ((c1.airmass <= airmass) and
                                       (c2.airmass <= airmass))))

    ## def observable(self, target, time_start, time_stop,
    ##                el_min_deg, el_max_deg, time_needed,
    ##                airmass=None):
    ##     res = self._observable(target, time_start, time_stop,
    ##                            el_min_deg, el_max_deg,
    ##                            airmass=airmass)
    ##     return res

    def observable2(self, target, time_start, time_stop,
                   el_min_deg, el_max_deg, time_needed,
                   airmass=None):
        """
        Return True if `target` is observable between `time_start` and
        `time_stop`, defined by whether it is between elevation `el_min`
        and `el_max` during that period (and whether it meets the minimum
        `airmass`), for the requested amount of `time_needed`.
        """
        delta = (time_stop - time_start).total_seconds()
        if time_needed > delta:
            return (False, None)
        
        time_off = 0
        time_inc = 300
        total_visible = 0
        cnt = 0
        pos = None

        # TODO: need a much more efficient algorithm than this
        # should be able to use calculated rise/fall times
        while time_off < delta:
            time_s = time_start + timedelta(0, time_off)
            time_left = (time_stop - time_s).total_seconds()
            incr = min(time_inc, time_left)
            time_e = time_s + timedelta(0, incr)
            res = self._observable(target, time_s, time_e,
                                   el_min_deg, el_max_deg,
                                   airmass=airmass)
            if res:
                total_visible += incr
                if pos == None:
                    pos = time_s
            time_off += incr

        if pos == None:
            return (False, None)
        elif time_needed > total_visible:
            return (False, pos)
        elif pos + timedelta(0, time_needed) < time_stop:
            return (True, pos)
        return (False, pos)

    def observable(self, target, time_start, time_stop,
                   el_min_deg, el_max_deg, time_needed,
                   airmass=None):
        """
        Return True if `target` is observable between `time_start` and
        `time_stop`, defined by whether it is between elevation `el_min`
        and `el_max` during that period, and whether it meets the minimum
        airmass. 
        """
        # set observer's horizon to elevation for el_min or to achieve
        # desired airmass
        # TODO: compute desired altitude from airmass
        min_alt_deg = el_min_deg
        site = self.get_site(date=time_start, horizon=min_alt_deg)

        d1 = self.calc(target, time_start)
        #print d1
        d2 = self.calc(target, time_stop)
        #print d2
        #print "---"

        # TODO: worry about el_max_deg
        
        if d1.alt_deg >= min_alt_deg:
            # body is above desired altitude at start of period
            # so calculate next setting
            time_rise = ephem.Date(time_start)
            time_set = site.next_setting(target.body, start=time_rise)

        else:
            # body is below desired altitude at start of period
            # so calculate next rising
            time_rise = site.next_rising(target.body, start=ephem.Date(time_start))
            time_set = site.next_setting(target.body, start=time_rise)

        # convert all times to pyephem dates so we can compare
        # last observable time is setting or end of period,
        # whichever comes first
        time_end = min(time_set, ephem.Date(time_stop))
        print time_rise, time_end
        # calculate duration in seconds (subtracting two pyephem Date
        # objects seems to give a fraction in days)
        duration = (time_end - time_rise) * 86400.0
        print "duration=%f sec" % (duration)
        # object is observable as long as the duration that it is
        # up is as long or longer than the time needed
        can_obs = (duration >= time_needed)
        # TODO: return time end as well
        return (can_obs, time_rise)


    def __repr__(self):
        return self.name

    __str__ = __repr__


class HST(tzinfo):
    """
    HST time zone info.  Used to construct times in HST for planning
    purposes.
    """
    def utcoffset(self, dt):
        return timedelta(hours=-10)
    
    def dst(self, dt):
        return timedelta(0)

    def tzname(self,dt):
         return "HST"


class TelescopeConfiguration(object):

    def __init__(self, focus=None):
        self.focus = focus
        self.min_el = 15.0
        self.max_el = 89.0
    
    def get_el_minmax(self):
        return (self.min_el, self.max_el)
        
class InstrumentConfiguration(object):

    def __init__(self):
        pass

class SPCAMConfiguration(InstrumentConfiguration):
    
    def __init__(self, filter=None):
        super(SPCAMConfiguration, self).__init__()

        self.insname = 'SPCAM'
        self.filter = filter
    
class EnvironmentConfiguration(object):

    def __init__(self, seeing=None, airmass=None):
        self.seeing = seeing
        self.airmass = airmass
    

#END
