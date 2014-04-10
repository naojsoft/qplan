#
# misc.py -- miscellaneous queue support functions
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import timedelta
import csv

# gen2 imports
from astro import radec

# local imports
import entity


def get_body_SOSS(name, ra_funky, dec_funky, equinox=2000):
    ra_deg = radec.funkyHMStoDeg(ra_funky)
    dec_deg = radec.funkyDMStoDeg(dec_funky)
    ra = radec.raDegToString(ra_deg, format='%02d:%02d:%06.3f')
    dec = radec.decDegToString(dec_deg, format='%s%02d:%02d:%05.2f')
    
    return get_body(name, ra, dec, equinox=equinox)


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

        for row in reader:
            (proposal, propid, origrank, newrank) = row
            programs[proposal] = entity.Program(proposal, propid=propid,
                                                rank=float(newrank))

    return programs


def parse_obs(filepath, propdict):
    """
    Read all observing blocks from a CSV file.
    """
    obs = []
    with open(filepath, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        # skip header
        next(reader)

        for row in reader:
            (proposal, name, ra, dec, eq, filter, exptime, num_exp,
             dither, totaltime, seeing, airmass) = row
            # skip blank lines
            if len(proposal.strip()) == 0:
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
            
            ob = entity.OB(program=propdict[proposal],
                           target=entity.StaticTarget(name, ra, dec, eq),
                           filter=filter,
                           total_time=float(totaltime),
                           seeing=seeing, airmass=airmass)
            obs.append(ob)

    return obs


#END
