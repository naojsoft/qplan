#
# misc.py -- miscellaneous queue support functions
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import timedelta
import csv
import string
import math

# 3rd party imports
import numpy

# gen2 imports
#from astro import radec

# local imports
import entity


# def get_body_SOSS(name, ra_funky, dec_funky, equinox=2000):
#     ra_deg = radec.funkyHMStoDeg(ra_funky)
#     dec_deg = radec.funkyDMStoDeg(dec_funky)
#     ra = radec.raDegToString(ra_deg, format='%02d:%02d:%06.3f')
#     dec = radec.decDegToString(dec_deg, format='%s%02d:%02d:%05.2f')
    
#     return get_body(name, ra, dec, equinox=equinox)


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


def parse_proposals(filepath):
    """
    Read all proposal information from a CSV file.
    """
    programs = {}
    with open(filepath, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        # skip header
        next(reader)
        lineno = 1

        try:
            for row in reader:
                lineno += 1
                (proposal, propid, rank, category, band, hours,
                 partner, skip) = row
                if skip.strip() != '':
                    continue
                programs[proposal] = entity.Program(proposal, propid=propid,
                                                    rank=float(rank),
                                                    band=int(band),
                                                    partner=partner,
                                                    category=category,
                                                    hours=float(hours))
        except Exception as e:
            raise ValueError("Error reading proposals at line %d: %s" % (
                lineno, str(e)))

    return programs


def parse_obs(filepath, proposal, propdict):
    """
    Read all observing blocks from a CSV file.
    """
    obs = []
    with open(filepath, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        # skip header
        next(reader)

        for row in reader:
            (obname, name, ra, dec, eq, filter, exptime, num_exp,
             dither, totaltime, priority, seeing, airmass, moon, sky) = row
            # skip blank lines
            obname = obname.strip()
            if len(obname) == 0:
                continue
            # skip comments
            if obname.lower() == 'comment':
                continue
            # transform equinox, e.g. "J2000" -> 2000
            if isinstance(eq, str):
                if eq[0] in ('B', 'J'):
                    eq = eq[1:]
                    eq = float(eq)
            eq = int(eq)
            
            if len(seeing.strip()) != 0:
                seeing = float(seeing)
            else:
                seeing = None
            
            if len(airmass.strip()) != 0:
                airmass = float(airmass)
            else:
                airmass = None

            if len(priority.strip()) != 0:
                priority = float(priority)
            else:
                priority = 1.0

            envcfg = entity.EnvironmentConfiguration(seeing=seeing,
                                                     airmass=airmass,
                                                     moon=moon, sky=sky)
            inscfg = entity.SPCAMConfiguration(filter=filter)
            telcfg = entity.TelescopeConfiguration(focus='P_OPT')
            
            ob = entity.OB(program=propdict[proposal],
                           target=entity.StaticTarget(name, ra, dec, eq),
                           inscfg=inscfg,
                           envcfg=envcfg,
                           telcfg=telcfg,
                           priority=priority,
                           name=obname,
                           total_time=float(totaltime))
            obs.append(ob)

    return obs

def parse_schedule(filepath):
    """
    Read the observing schedule from a CSV file.
    """
    schedule = []
    with open(filepath, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        # skip header
        next(reader)

        line = 1
        for row in reader:
            try:
                (date, starttime, stoptime, categories, filters, skycond,
                 seeing, note) = row

            except Exception as e:
                raise ValueError("Error reading line %d of schedule: %s" % (
                    line, str(e)))

            line += 1
            # skip blank lines
            if len(date.strip()) == 0:
                continue

            filters = map(string.strip, filters.split(','))
            seeing = float(seeing)
            categories = categories.replace(' ', '').lower().split(',')

            # TEMP: skip non-OPEN categories
            if not 'open' in categories:
                continue
            
            rec = (date, starttime, stoptime, categories, filters,
                   seeing, skycond)
            schedule.append(rec)

    return schedule


def alt2airmass(alt_deg):
    xp = 1.0 / math.sin(math.radians(alt_deg + 244.0/(165.0 + 47*alt_deg**1.1)))
    return xp
    
am_inv = []
for alt in range(0, 91):
    alt_deg = float(alt)
    am = alt2airmass(alt_deg)
    am_inv.append((am, alt_deg))

def airmass2alt(am):
    for (x, alt_deg) in am_inv:
        if x <= am:
            return alt_deg
    return 90.0

def calc_slew_time(d_az, d_el, rate_az=0.5, rate_el=0.5):
    """Calculate slew time given a delta in azimuth aand elevation.
    """
    time_sec = max(math.fabs(d_el) / rate_el,
                   math.fabs(d_az) / rate_az)
    return time_sec


#END
