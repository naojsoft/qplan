#
# misc.py -- miscellaneous queue support functions
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import datetime, timedelta

# 3rd party imports
import ephem

# gen2 imports
from astro import radec

# local imports
import entity


def get_observer(date, horizon=None):
    subaru_obs = ephem.Observer()
    subaru_obs.lon = '-155:28:48.900'
    subaru_obs.lat = '+19:49:42.600'
    subaru_obs.elevation = 4139
    yr, mo, da, hr, mn, sc = tuple(date.utctimetuple()[:6])
    subaru_obs.date = '%4.4d/%02d/%02d %02d:%02d:%02d' % (
        yr, mo, da, hr, mn, sc)

    # set horizon to minimum observing altitude of horizon
    if horizon != None:
        horiz_amin = horizon * radec.degPerHMSSec
        subaru_obs.horizon = '+%.4f' % (horiz_amin)

    subaru_obs.compute_pressure()
    return subaru_obs


def get_twilight(date):
    sobs = get_observer(date, horizon=-18.0)
    t1 = sobs.previous_rising(ephem.Sun(), use_center=True)
    t2 = sobs.next_setting(ephem.Sun(), use_center=True)
    return (t1, t2)


def observable(body, time_start, time_stop, el_min, el_max):
    """
    Return True if `body` is observable between `time_start` and `time_stop`,
    defined by whether it is between elevation `el_min` and `el_max` during
    that period.
    """
    sobs = get_observer(time_start)
    body.compute(sobs)
    alt1 = radec.dmsStrToDeg(str(body.alt))
    
    sobs = get_observer(time_stop)
    body.compute(sobs)
    alt2 = radec.dmsStrToDeg(str(body.alt))
    #print "alt start, stop = %.2f, %.2f" % (alt1, alt2)

    return (el_min <= alt1 <= el_max) and (el_min <= alt1 <= el_max)


def get_body(name, ra, dec, equinox=2000):
    # make up a magnitude--doesn't matter
    mag = 15.0

    xeph_line = "%s,f,%s,%s,%f,%d" % (name[:20], ra, dec, mag, int(equinox))
    return ephem.readdb(xeph_line)


def get_body_SOSS(name, ra_funky, dec_funky, equinox=2000):
    ra_deg = radec.funkyHMStoDeg(ra_funky)
    dec_deg = radec.funkyDMStoDeg(dec_funky)
    ra = radec.raDegToString(ra_deg, format='%02d:%02d:%06.3f')
    dec = radec.decDegToString(dec_deg, format='%s%02d:%02d:%05.2f')
    
    return get_body(name, ra, dec, equinox=equinox)


def get_date(s):
    formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H',
               '%Y-%m-%d']
    for fmt in formats:
        try:
            date = datetime.strptime(s, fmt)

            timetup = tuple(date.timetuple()[:6])
            # re-express as HST
            date = datetime(*timetup, tzinfo=entity.HST())
            return date
        except ValueError as e:
            continue

    raise e


def make_slots(start_time, night_length_mn, min_slot_length_sc):
    """
    Parameters
    ----------
    start_time : datetime.datetime
       Start of observation
    night_length_mn : int
        Night length in MINUTES
    min_slot_length_sc : int
        Slot length in SECONDS
    """
    night_slots = []
    for isec in range(0, night_length_mn*60, min_slot_length_sc):
        slot_start = start_time + timedelta(0, isec)
        night_slots.append(entity.Slot(slot_start, min_slot_length_sc))
    
    return night_slots

#END
