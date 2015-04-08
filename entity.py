#
# entity.py -- various entities used by queue system
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import tzinfo, timedelta, datetime
import string

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
    def __init__(self, proposal, pi='', observers='', rank=1.0, 
                 propid=None, grade=None, partner=None, hours=None,
                 category=None, instruments=[], description=None):
        super(Program, self).__init__()
        
        self.proposal = proposal
        if propid == None:
            # TODO: is there an algorithm to turn proposals
            # into propids?
            propid = proposal
        self.propid = propid
        self.pi = pi
        self.observers = observers
        self.rank = rank
        self.grade = grade
        self.partner = partner
        self.category = category.lower()
        self.instruments = map(string.upper, instruments)
        self.total_time = hours * 3600.0
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
        super(Slot, self).__init__()
        self.start_time = start_time
        self.stop_time = start_time + timedelta(0, slot_len_sec)
        self.data = data
        self.ob = None

    def set_ob(self, ob):
        self.ob = ob

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
            diff = (start_time - self.start_time).total_seconds()
            if math.fabs(diff) < 5.0:
                start_time = self.start_time
            else:
                raise SlotError("Start time (%s) < slot start time (%s) diff=%f" % (
                    start_time, self.start_time, diff))

        stop_time = start_time + timedelta(0, slot_len_sec)
        if stop_time > self.stop_time:
            raise SlotError("Stop time (%s) > slot stop time (%s)" % (
                stop_time, self.stop_time))

        # define before slot
        slot_b = None
        diff = (start_time - self.start_time).total_seconds()
        # Don't create a slot for less than a minute in length
        if diff > 1.0:
            diff_sec = (start_time - self.start_time).total_seconds()
            slot_b = Slot(self.start_time, diff_sec, data=self.data)

        # define new displacing slot
        slot_c = Slot(start_time, slot_len_sec, data=self.data)

        # define after slot
        slot_d = None
        diff = (self.stop_time - stop_time).total_seconds()
        # Don't create a slot for less than a minute in length
        if diff > 1.0:
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


class Schedule(object):
    """
    Schedule
    Defines a series of slots and operations on that series.
    
    """
    def __init__(self, start_time, stop_time, data=None):
        super(Schedule, self).__init__()
        self.start_time = start_time
        self.stop_time = stop_time
        self.data = data

        diff = (self.stop_time - self.start_time).total_seconds()
        self.waste = diff
        self.slots = []

    def num_slots(self):
        return len(self.slots)
    
    def get_free(self):
        if len(self.slots) == 0:
            return self.start_time, self.stop_time

        last = self.slots[-1]
        return last.stop_time, self.stop_time

    def next_free_slot(self):
        start_time, stop_time = self.get_free()
        diff = (stop_time - start_time).total_seconds()
        if diff <= 0.0:
            return None
        return Slot(start_time, diff)
        
    def _previous(self, slot):
        if len(self.slots) == 0:
            return -1, None

        # TODO: in the typical insertion case, would the search
        # be faster from the rear?
        for i in xrange(len(self.slots)):
            slot_i = self.slots[i]
            if slot_i.start_time > slot.start_time:
                if i == 0:
                    return -1, None
                return i-1, self.slots[i-1]

        return i, slot_i

    def get_previous(self, slot):
        i, slot_i = self._previous(slot)
        return slot_i

    def _next(self, slot):
        for i in xrange(len(self.slots)):
            slot_i = self.slots[i]
            if slot_i.start_time > slot.start_time:
                return i, slot_i

        return len(self.slots), None
    
    def get_next(self, slot):
        i, slot_i = self._next(slot)
        return slot_i
    
    def insert_slot(self, slot):
        i, prev_slot = self._previous(slot)
        if prev_slot != None:
            interval = (slot.start_time - prev_slot.stop_time).total_seconds()
            assert interval >= 0, \
                   ValueError("Slot overlaps end of previous slot by %d sec" % (
                -interval))

        if i+1 < self.num_slots():
            next_slot = self.slots[i]
            interval = (next_slot.start_time - slot.stop_time).total_seconds()
            ## assert interval >= 0, \
            ##     ValueError("Slot overlaps start of next slot by %d sec" % (
            ##     -interval))

        self.slots.insert(i+1, slot)
        self.waste -= slot.size()

    ## def append_slot(self, slot):
    ##     start_time, stop_time = self.get_free()
    ##     if slot.start_time > start_time:
    ##         # there is some gap between our last slot and this one
    ##         # so insert an empty slot
    ##         diff = (slot.start_time - start_time).total_seconds()
    ##         self.slots.append(Slot(start_time, diff))

    ##     self.slots.append(slot)
    ##     self.waste -= slot.size()
        
    def copy(self):
        newsch = Schedule(self.start_time, self.stop_time)
        newsch.waste = self.waste
        newsch.data  = self.data
        newsch.slots = list(self.slots)

    def get_waste(self):
        ## start_time, stop_time = self.get_free()
        ## total = (stop_time - start_time).total_seconds()

        ## for slot in self.slots:
        ##     if slot.data == None:
        ##         total += slot.size()

        ## return total
        return self.waste

    def __repr__(self):
        s = self.start_time.strftime("%Y-%m-%d %H:%M")
        return s

    __str__ = __repr__


class OB(object):
    """
    Observing Block
    Defines an item that can be scheduled during the night.
    
    """
    count = 1
    
    def __init__(self, id=None, program=None, target=None, telcfg=None,
                 inscfg=None, envcfg=None, total_time=None,
                 priority=1.0, name=None, derived=None, comment=''):
        super(OB, self).__init__()
        if id is None:
            id = "ob%04d" % (OB.count)
            OB.count += 1
        self.id = id
        
        self.program = program
        self.priority = priority
        if name == None:
            name = self.id
        self.name = name

        # constraints
        self.target = target
        self.inscfg = inscfg
        self.telcfg = telcfg
        self.envcfg = envcfg
        self.total_time = total_time

        # other fields
        self.derived = derived
        self.comment = comment
        self.status = 'new'
        self.data_quality = 0

    def __repr__(self):
        return self.id

    __str__ = __repr__


class BaseTarget(object):
    pass
    
class StaticTarget(object):
    def __init__(self, name=None, ra=None, dec=None, equinox=2000.0):
        super(StaticTarget, self).__init__()
        self.name = name
        self.ra = ra
        self.dec = dec
        self.equinox = equinox

        if self.ra is not None:
            self._recalc_body()

    def _recalc_body(self):
        self.xeph_line = "%s,f|A,%s,%s,0.0,%s" % (
            self.name[:20], self.ra, self.dec, self.equinox)
        self.body = ephem.readdb(self.xeph_line)


    def import_record(self, rec):
        code = rec.code.strip()
        self.name = rec.name
        self.ra = rec.ra
        self.dec = rec.dec
        
        # transform equinox, e.g. "J2000" -> 2000
        eq = rec.eq
        if isinstance(eq, str):
            eq = eq.upper()
            if eq[0] in ('B', 'J'):
                eq = eq[1:]
                eq = float(eq)
        eq = int(eq)
        self.equinox = eq

        self._recalc_body()
        return code

    def calc(self, observer, time_start):
        return CalculationResult(self, observer, time_start)

    # for pickling
    
    def __getstate__(self):
        d = self.__dict__.copy()
        # ephem objects can't be pickled
        d['body'] = None
        return d
        
    def __setstate__(self, state):
        self.__dict__.update(state)
        self.body = ephem.readdb(self.xeph_line)


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
        self.horizon = -1 * numpy.sqrt(2 * elevation / ephem.earth_radius)

        #self.tz_local = pytz.timezone(self.timezone)
        self.tz_local = timezone
        self.tz_utc = pytz.timezone('UTC')
        self.site = self.get_site(date=date)

        # used for sunset, sunrise calculations
        self.horizon12 = -1.0*ephem.degrees('12:00:00.0')
        self.horizon18 = -1.0*ephem.degrees('18:00:00.0')
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
        if date == None:
            date = datetime.now()
            date.replace(tzinfo=self.tz_utc)
        site.date = ephem.Date(date)
        return site
        
    def set_date(self, date):
        try:
            date = date.astimezone(self.tz_utc)
        except Exception:
            date = self.tz_utc.localize(date)
        self.date = date
        self.site.date = ephem.Date(date)
        
    def calc(self, body, time_start):
        return body.calc(self, time_start)
    
    def get_date(self, date_str, timezone=None):
        if timezone == None:
            timezone = self.tz_local

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

    def observable_now(self, target, time_start, time_needed,
                       el_min_deg, el_max_deg, airmass=None):

        time_stop = time_start + timedelta(0, time_needed)
        res = self._observable(target, time_start, time_stop,
                               el_min_deg, el_max_deg,
                               airmass=airmass)
        return res

    ## def observable2(self, target, time_start, time_stop,
    ##                el_min_deg, el_max_deg, time_needed,
    ##                airmass=None):
    ##     """
    ##     Return True if `target` is observable between `time_start` and
    ##     `time_stop`, defined by whether it is between elevation `el_min`
    ##     and `el_max` during that period (and whether it meets the minimum
    ##     `airmass`), for the requested amount of `time_needed`.
    ##     """
    ##     delta = (time_stop - time_start).total_seconds()
    ##     if time_needed > delta:
    ##         return (False, None)
        
    ##     time_off = 0
    ##     time_inc = 300
    ##     total_visible = 0
    ##     cnt = 0
    ##     pos = None

    ##     # TODO: need a much more efficient algorithm than this
    ##     # should be able to use calculated rise/fall times
    ##     while time_off < delta:
    ##         time_s = time_start + timedelta(0, time_off)
    ##         time_left = (time_stop - time_s).total_seconds()
    ##         incr = min(time_inc, time_left)
    ##         time_e = time_s + timedelta(0, incr)
    ##         res = self._observable(target, time_s, time_e,
    ##                                el_min_deg, el_max_deg,
    ##                                airmass=airmass)
    ##         if res:
    ##             total_visible += incr
    ##             if pos == None:
    ##                 pos = time_s
    ##         time_off += incr

    ##     if pos == None:
    ##         return (False, None)
    ##     elif time_needed > total_visible:
    ##         return (False, pos)
    ##     elif pos + timedelta(0, time_needed) < time_stop:
    ##         return (True, pos)
    ##     return (False, pos)

    ## def totz(self, date):
    ##     local_tz = pytz.timezone('US/Hawaii')
    ##     return local_tz.localize(date.datetime())

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
            alt_deg = misc.airmass2alt(airmass)
            min_alt_deg = max(alt_deg, el_min_deg)
        else:
            min_alt_deg = el_min_deg
    
        site = self.get_site(date=time_start, horizon_deg=min_alt_deg)

        d1 = self.calc(target, time_start)

        # TODO: worry about el_max_deg

        # important: pyephem only deals with UTC!!
        time_start_utc = ephem.Date(time_start.astimezone(self.tz_utc))
        time_stop_utc = ephem.Date(time_stop.astimezone(self.tz_utc))
        #print "period (UT): %s to %s" % (time_start_utc, time_stop_utc)
        
        if d1.alt_deg >= min_alt_deg:
            # body is above desired altitude at start of period
            # so calculate next setting
            time_rise = time_start_utc
            time_set = site.next_setting(target.body, start=time_start_utc)
            #print "body already up: set=%s" % (time_set)

        else:
            # body is below desired altitude at start of period
            try:
                time_rise = site.next_rising(target.body, start=time_start_utc)
                time_set = site.next_setting(target.body, start=time_start_utc)
            except ephem.NeverUpError:
                return (False, None, None)
            
            #print "body not up: rise=%s set=%s" % (time_rise, time_set)
            ## if time_rise < time_set:
            ##     print "body still rising, below threshold"
            ##     # <-- body is still rising, just not high enough yet
            ## else:
            ##     # <-- body is setting
            ##     print "body setting, below threshold"
            ##     # calculate rise time backward from end of period
            ##     #time_rise = site.previous_rising(target.body, start=time_stop_utc)
            ##     pass

        if time_rise < time_start_utc:
            diff = time_rise - time_start_utc
            ## raise AssertionError("time rise (%s) < time start (%s)" % (
            ##         time_rise, time_start))
            print ("WARNING: time rise (%s) < time start (%s)" % (
                    time_rise, time_start))
            time_rise = time_start_utc

        # last observable time is setting or end of period,
        # whichever comes first
        time_end = min(time_set, time_stop_utc)
        # calculate duration in seconds (subtracting two pyephem Date
        # objects seems to give a fraction in days)
        duration = (time_end - time_rise) * 86400.0
        # object is observable as long as the duration that it is
        # up is as long or longer than the time needed
        diff = duration - float(time_needed)
        #can_obs = diff > -0.001
        can_obs = duration > time_needed
        #print "can_obs=%s duration=%f needed=%f diff=%f" % (
        #    can_obs, duration, time_needed, diff)

        # convert time_rise back to a datetime
        time_rise = self.tz_utc.localize(time_rise.datetime())
        return (can_obs, time_rise, time_end)

    def distance(self, tgt1, tgt2, time_start):
        c1 = self.calc(tgt1, time_start)
        c2 = self.calc(tgt2, time_start)

        d_alt = c1.alt_deg - c2.alt_deg
        d_az = c1.az_deg - c2.az_deg
        return (d_alt, d_az)
    
    def sunset(self, date=None):
        """Sunset in UTC"""
        self.site.horizon = self.horizon
        if date is None:
            date = self.date
        self.site.date = date
        r_date = self.site.next_setting(self.sun)
        return r_date

    def sunrise(self, date=None):
        """Sunrise in UTC"""
        self.site.horizon = self.horizon
        if date is None:
            date = self.date
        self.site.date = date
        r_date = self.site.next_rising(self.sun)
        return r_date
        
    def evening_twilight_12(self, date=None):
        """Evening 12 degree (nautical) twilight in UTC"""
        self.site.horizon = self.horizon12
        if date is None:
            date = self.date
        self.site.date = date
        r_date = self.site.next_setting(self.sun)
        return r_date

    def evening_twilight_18(self, date=None):
        """Evening 18 degree (civil) twilight"""
        self.site.horizon = self.horizon18
        if date is None:
            date = self.date
        self.site.date = date
        r_date = self.site.next_setting(self.sun)
        return r_date

    def morning_twilight_12(self, date=None):
        """Morning 12 degree (nautical) twilight in UTC"""
        self.site.horizon = self.horizon12
        if date is None:
            date = self.date
        self.site.date = date
        r_date = self.site.next_rising(self.sun)
        return r_date

    def morning_twilight_18(self, date=None):
        """Morning 18 degree (civil) twilight in UTC"""
        self.site.horizon = self.horizon18
        if date is None:
            date = self.date
        self.site.date = date
        r_date = self.site.next_rising(self.sun)
        return r_date

    def sun_set_rise_times(self, date=None, local=False):
        """Sunset, sunrise and twilight times. Returns a tuple with (sunset, 12d, 18d, 18d, 12d, sunrise).
        Default times in UTC. If local=True returns times in local timezone"""
        if local:
            rstimes =  (self.utc2local(self.sunset(date=date)),
                        self.utc2local(self.evening_twilight_12(date=date)),
                        self.utc2local(self.evening_twilight_18(date=date)), 
                        self.utc2local(self.morning_twilight_18(date=date)),
                        self.utc2local(self.morning_twilight_12(date=date)),
                        self.utc2local(self.sunrise(date=date)))
        else:
            rstimes =  (self.sunset(date=date),
                        self.evening_twilight_12(date=date),
                        self.evening_twilight_18(date=date), 
                        self.morning_twilight_18(date=date),
                        self.morning_twilight_12(date=date),
                        self.sunrise(date=date))
        return rstimes

    def moon_rise(self, date=None):
        """Moon rise time in UTC"""
        if date is None:
            date = self.date
        self.site.date = date
        moonrise = self.site.next_rising(self.moon)
        if moonrise < self.sunset():
            None
        return moonrise

    def moon_set(self, date=None):
        """Moon set time in UTC"""
        if date is None:
            date = self.date
        self.site.date = date
        moonset = self.site.next_setting(self.moon)
        if moonset > self.sunrise():
            moonset = None
        return moonset
    
    def moon_phase(self, date=None):
        """Moon percentage of illumination"""
        if date is None:
            date = self.date
        self.site.date = date
        return self.moon.moon_phase

    def night_center(self, date=None):
        """Compute night center"""
        return (self.sunset(date=date) + self.sunrise(date=date))/2.0
            
    def local2utc(self, date_s):
        """Convert local time to UTC"""
        y, m, d = date_s.split('/')
        tlocal = datetime(int(y), int(m), int(d), 12, 0, 0,
                          tzinfo=self.tz_local)
        r_date = ephem.Date(tlocal.astimezone(self.tz_utc))
        return r_date
        
    def utc2local(self, date_time):
        """Convert UTC to local time"""
        if date_time != None:
            dt = date_time.datetime()
            utc_dt = datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                              dt.second, dt.microsecond, tzinfo=self.tz_utc)
            r_date = ephem.Date(utc_dt.astimezone(self.tz_local))
            return r_date
        else:
            return None
    
    def get_text_almanac(self, date):
        date_s = date.strftime("%Y-%m-%d")
        text = ''
        text += 'Almanac for the night of %s\n' % date_s.split()[0]
        text += '\nEvening\n'
        text += '_'*30 + '\n'
        rst = self.sun_set_rise_times(date=date, local=True)
        rst = [t.datetime().strftime('%H:%M') for t in rst]
        text += 'Sunset: %s\n12d: %s\n18d: %s\n' % (rst[0], rst[1], rst[2])
        text += '\nMorning\n'
        text += '_'*30 + '\n'
        text += '18d: %s\n12d: %s\nSunrise: %s\n' % (rst[3], rst[4], rst[5])
        return text
        
    def get_target_info(self, target, time_start=None, time_stop=None,
                        time_interval=5):
        """Compute various values for a target from sunrise to sunset"""

        def _set_time(dtime):
            # Sets time to nice rounded value
            y, m ,d, hh, mm, ss = dtime.tuple()
            mm = mm - (mm % 5)
            return ephem.Date(datetime(y, m , d, hh, mm, 5, 0))

        def _set_data_range(sunset, sunrise, tint):
            # Returns numpy array of dates 15 minutes before sunset
            # and after sunrise
            ss = _set_time(ephem.Date(sunset - 15*ephem.minute))
            sr = _set_time(ephem.Date(sunrise + 15*ephem.minute))
            return numpy.arange(ss, sr, tint)
    
        if time_start == None:
            # default for start time is sunset on the current date
            time_start = self.sunset()
        if time_stop == None:
            # default for stop time is sunrise on the current date
            time_stop = self.sunrise(date=time_start)
            
        t_range = _set_data_range(time_start, time_stop,
                                  time_interval*ephem.minute)
        #print('computing airmass history...')
        history = []

        # TODO: this should probably return a generator
        for ut in t_range:
            # ugh
            tup = ephem.Date(ut).tuple()
            args = tup[:-1] + (int(tup[-1]),)
            ut_with_tz = datetime(*args,
                                  tzinfo=self.tz_utc)
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
            s_lt = info.lt.datetime().strftime('%d%b%Y  %H:%M')
            s_utc = info.ut.datetime().strftime('%H:%M')
            s_ha = ':'.join(str(ephem.hours(info.ha)).split(':')[:2])
            s_lst = ':'.join(str(ephem.hours(info.lst)).split(':')[:2])
            s_pa = round(info.pang*180.0/numpy.pi, 1)
            s_am = round(info.airmass, 2)
            s_ma = round(info.moon_alt*180.0/numpy.pi, 1)
            if s_ma < 0:
                s_ma = ''
            s_data = format % (s_lt, s_utc, s_lst, s_ha, s_pa, s_am, s_ma)
            text += s_data
        return text

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

    def tzname(self, dt):
         return 'HST'

    def upper(self):
         return 'HST'


class TelescopeConfiguration(object):

    def __init__(self, focus=None, dome=None):
        super(TelescopeConfiguration, self).__init__()
        self.focus = focus
        if dome is None:
            dome = 'open'
        else:
            dome = dome.lower()
        self.dome = dome
        self.min_el = 15.0
        self.max_el = 89.0
    
    def get_el_minmax(self):
        return (self.min_el, self.max_el)

    def import_record(self, rec):
        code = rec.code.lower()
        self.focus = rec.focus.upper()
        self.dome = rec.dome.lower()
        return code
        
class InstrumentConfiguration(object):

    def __init__(self):
        super(InstrumentConfiguration, self).__init__()

        self.insname = None
        self.mode = None

class SPCAMConfiguration(InstrumentConfiguration):
    
    def __init__(self, filter=None, guiding=False, num_exp=1, exp_time=10,
                 mode='IMAGE', offset_ra=0, offset_dec=0, pa=90,
                 dith1=60, dith2=None):
        super(SPCAMConfiguration, self).__init__()

        self.insname = 'SPCAM'
        if filter is not None:
            filter = filter.lower()
        self.filter = filter
        self.dither = dither
        self.guiding = guiding
        self.num_exp = num_exp
        self.exp_time = exp_time
        self.mode = mode
        self.offset_ra = offset_ra
        self.offset_dec = offset_dec
        self.pa = pa
        self.dith1 = dith1
        if dith2 == None:
            # TODO: defaults for this depends on mode
            dith2 = 0
        self.dith2 = dith2

    def calc_filter_change_time(self):
        # TODO: this needs to become more accurate
        filter_change_time_sec = 10.0 * 60.0
        return filter_change_time_sec

class HSCConfiguration(InstrumentConfiguration):
    
    def __init__(self, filter=None, guiding=False, num_exp=1, exp_time=10,
                 mode='IMAGE', dither=1, offset_ra=0, offset_dec=0, pa=90,
                 dith1=60, dith2=None):
        super(HSCConfiguration, self).__init__()

        self.insname = 'HSC'
        self.mode = mode
        if filter is not None:
            filter = filter.lower()
        self.filter = filter
        self.dither = dither
        self.guiding = guiding
        self.num_exp = int(num_exp)
        self.exp_time = float(exp_time)
        self.offset_ra = offset_ra
        self.offset_dec = offset_dec
        self.pa = pa
        self.dith1 = dith1
        if dith2 == None:
            # TODO: defaults for this depends on mode
            dith2 = 0
        self.dith2 = dith2
    
    def calc_filter_change_time(self):
        # TODO: this needs to become more accurate
        filter_change_time_sec = 35.0 * 60.0
        return filter_change_time_sec

    def import_record(self, rec):
        code = rec.code.lower()
        self.insname = 'HSC'
        self.filter = rec.filter.lower()
        self.mode = rec.mode
        self.dither = rec.dither
        self.guiding = rec.guiding in ('y', 'Y', 'yes', 'YES')
        self.num_exp = int(rec.num_exp)
        self.exp_time = float(rec.exp_time)
        self.pa = float(rec.pa)
        self.offset_ra = float(rec.offset_ra)
        self.offset_dec = float(rec.offset_dec)
        self.dith1 = float(rec.dith1)
        self.dith2 = float(rec.dith2)
        return code

class FOCASConfiguration(InstrumentConfiguration):
    
    def __init__(self, filter=None, guiding=False, num_exp=1, exp_time=10,
                 mode='IMAGE', binning='1x1', offset_ra=0, offset_dec=0,
                 pa=0, dither_ra=5, dither_dec=5, dither_theta=0.0):
        super(FOCASConfiguration, self).__init__()

        self.insname = 'FOCAS'
        self.mode = mode
        if filter is not None:
            filter = filter.lower()
        self.filter = filter
        self.guiding = guiding
        self.num_exp = int(num_exp)
        self.exp_time = float(exp_time)
        self.pa = float(pa)
        self.binning = binning
        self.offset_ra = float(offset_ra)
        self.offset_dec = float(offset_dec)
        self.dither_ra = float(dither_ra)
        self.dither_dec = float(dither_dec)
        self.dither_theta = float(dither_theta)

    def calc_filter_change_time(self):
        # TODO: this needs to become more accurate
        filter_change_time_sec = 30.0
        return filter_change_time_sec

    def import_record(self, rec):
        code = rec.code.lower()
        self.insname = 'FOCAS'
        self.mode = rec.mode
        self.filter = rec.filter.lower()
        self.guiding = rec.guiding in ('y', 'Y', 'yes', 'YES')
        self.num_exp = int(rec.num_exp)
        self.exp_time = float(rec.exp_time)
        self.pa = float(rec.pa)
        self.offset_ra = float(rec.offset_ra)
        self.offset_dec = float(rec.offset_dec)
        self.dither_ra = float(rec.dither_ra)
        self.dither_dec = float(rec.dither_dec)
        self.dither_theta = float(rec.dither_theta)
        self.binning = rec.binning
        return code

class EnvironmentConfiguration(object):

    def __init__(self, seeing=None, airmass=None, moon='any', 
                 transparency=None, moon_sep=None):
        super(EnvironmentConfiguration, self).__init__()
        self.seeing = seeing
        self.airmass = airmass
        self.transparency = transparency
        self.moon_sep = moon_sep
        if (moon == None) or (len(moon) == 0):
            moon = 'any'
        self.moon = moon.lower()

    def import_record(self, rec):
        code = rec.code.strip()

        seeing = rec.seeing.strip()
        if len(seeing) != 0:
            self.seeing = float(seeing)
        else:
            self.seeing = None

        airmass = rec.airmass.strip()
        if len(airmass) != 0:
            self.airmass = float(airmass)
        else:
            self.airmass = None

        self.moon = rec.moon
        self.moon_sep = float(rec.moon_sep)
        self.transparency = float(rec.transparency)
        return code


class CalculationResult(object):

    def __init__(self, target, observer, date):
        # TODO: make a COPY of observer.site
        self.observer = observer
        self.site = observer.site
        self.body = target.body
        self.date = date

        # Can/should this calculation be postponed?
        observer.set_date(date)
        self.body.compute(self.site)

        self.lt = self.date.astimezone(observer.tz_local)
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
            self._ut = self.lt.astimezone(pytz.utc)
        return self._ut

    @property
    def gmst(self):
        if self._gmst is None:
            jd = ephem.julian_date(self.ut)
            T = (jd - 2451545.0)/36525.0
            gmstdeg = 280.46061837+(360.98564736629*(jd-2451545.0))+(0.000387933*T*T)-(T*T*T/38710000.0)
            self._gmst = ephem.degrees(gmstdeg*numpy.pi/180.0)
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
    
    def calc_moon(self, site, body):
        """Compute Moon altitude"""
        moon = ephem.Moon()
        self.observer.set_date(self.date)
        moon.compute(site)
        moon_alt = math.degrees(float(moon.alt))
        # moon.phase is % of moon that is illuminated
        moon_pct = moon.moon_phase
        # calculate distance from target
        moon_sep = ephem.separation(moon, body)
        moon_sep = math.degrees(float(moon_sep))
        return (moon_alt, moon_pct, moon_sep)
        
    def calc_separation_alt_az(self, target):
        """Compute deltas for azimuth and altitude from another target"""
        self.target.body.compute(self.observer.site)
        target.body.compute(self.observer.site)

        delta_az = float(self.body.az) - float(target.az)
        delta_alt = float(self.body.alt) - float(target.alt)
        return (delta_alt, delta_az)
        
#END
