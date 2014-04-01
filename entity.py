#
# entity.py -- various entities used by queue system
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import tzinfo, timedelta

# local imports
import misc


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


class MSB(object):
    """
    Minimum Schedulable Block
    Defines the minimum item that can be scheduled during the night.
    
    """
    count = 0
    
    def __init__(self, program, filter=None, target=None,
                 min_el=15.0):
        self.id = "msb%04d" % (MSB.count)
        MSB.count += 1
        
        self.program = program
        self.filter = filter
        self.target = target

        # constraints
        self.min_el = 15.0
        
        
    def __repr__(self):
        return self.id

    __str__ = __repr__


class Slot(object):
    """
    Slot -- a period of the night that can be scheduled.
    Defined by a start time and a duration in seconds.
    """
    
    def __init__(self, start_time, slot_len_sec):
        self.start_time = start_time
        self.stop_time = start_time + timedelta(0, slot_len_sec)

    def __repr__(self):
        #s = self.start_time.strftime("%H:%M:%S")
        s = self.start_time.strftime("%H:%M")
        return s

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


class BaseTarget(object):
    pass
    
class StaticTarget(object):
    def __init__(self, name, ra, dec, equinox):
        self.name = name
        self.ra = ra
        self.dec = dec
        self.equinox = equinox

    def get_body(self):
        return misc.get_body(self.name, self.ra, self.dec,
                             equinox=self.equinox)
    
#END
