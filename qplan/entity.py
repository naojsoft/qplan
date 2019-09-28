#
# entity.py -- various entities used by queue system
#
#  Eric Jeschke (eric@naoj.org)
#
from datetime import timedelta, datetime
import math
import dateutil.parser
from dateutil import tz

# 3rd party imports
from ginga.util import wcs

entity_version = 20180618.0

from ginga.misc import Bunch

# local imports
from qplan.util.calcpos import Body, Observer

"""
NOTES
[1] MongoDB stores times in UTC (as epoch values actually).  Need to
    reattach time zone for datetime objects that are round-tripped from
    there.

"""

def explode(item):
    return {key: val
            for key, val in item.__dict__.items()
            if not key.startswith('_')}


class PersistentEntity(object):

    def __init__(self, tblname):
        super(PersistentEntity, self).__init__()
        self._tblname = tblname

    def to_rec(self):
        return explode(self)

    def from_rec(self, doc):
        self.__dict__.update(doc)

    def save(self, qt):
        qt.put(self)


class Program(PersistentEntity):
    """
    Program
    Defines a program that has been accepted for observation.
    """
    def __init__(self, proposal, pi='', observers='', rank=1.0,
                 propid=None, grade=None, partner=None, hours=0.0,
                 category='', instruments=[], description=None,
                 skip=False):
        super(Program, self).__init__('program')

        self.proposal = proposal
        if propid is None:
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
        self.instruments = [str.upper(s) for s in instruments]
        self.total_time = hours * 3600.0
        # TODO: eventually this will contain all the relevant info
        # pertaining to a proposal
        self.skip = skip

    @property
    def key(self):
        return dict(proposal=self.proposal)

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
        s = self.start_time.strftime("%Y-%m-%d %H:%M") + ("(%.2fm)" % duration)
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
        for i in range(len(self.slots)):
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
        for i in range(len(self.slots)):
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
        ##     if slot.data is None:
        ##         total += slot.size()

        ## return total
        return self.waste

    def __repr__(self):
        s = self.start_time.strftime("%Y-%m-%d %H:%M")
        return s

    __str__ = __repr__


class OB(PersistentEntity):
    """
    Observing Block
    Defines an item that can be scheduled during the night.

    """
    count = 1

    def __init__(self, id=None, program=None, target=None, telcfg=None,
                 inscfg=None, envcfg=None, calib_tgtcfg=None,
                 calib_inscfg=None, total_time=None, acct_time=None,
                 priority=1.0, name=None, derived=None, comment='',
                 extra_params=''):
        super(OB, self).__init__('ob')
        if id is None:
            id = "ob%d" % (OB.count)
            OB.count += 1
        self.id = id

        # these two items make up the primary key of an OB
        self.program = program
        if name is None:
            name = self.id
        self.name = name

        self.priority = priority

        # constraints
        self.target = target
        self.inscfg = inscfg
        self.telcfg = telcfg
        self.envcfg = envcfg

        # this can be None, "default" or a valid target configuration
        if calib_tgtcfg == 'default':
            # default calib_tgtcfg is same pointing as science target,
            # but name is prefixed with "calib for "
            calib_tgtcfg = HSCTarget(name="calib for %s" % target.name,
                                     ra=target.ra, dec=target.dec,
                                     equinox=target.equinox)
        self.calib_tgtcfg = calib_tgtcfg

        if calib_inscfg == 'default':
            # default calib_inscfg is a 30 sec single shot with same
            # filter as the science inscfg
            calib_inscfg = HSCConfiguration(filter=inscfg.filter,
                                            guiding=False, num_exp=1,
                                            exp_time=30,
                                            mode='IMAGE', dither='1',
                                            pa=inscfg.pa,
                                            comment='default 30 sec calib shot')

        elif calib_inscfg is None:
            if calib_tgtcfg is not None:
                raise ValueError("No calib_inscfg, but calib_tgtcfg specified")

        else:
            if calib_inscfg.filter != inscfg.filter:
                raise ValueError("calib_inscfg specifies different filter")
        self.calib_inscfg = calib_inscfg

        # other fields
        self.total_time = total_time
        self.derived = derived
        self.comment = comment
        self.acct_time = acct_time
        self.extra_params = extra_params

    @property
    def key(self):
        return dict(program=self.program.proposal, name=self.name)

    def to_rec(self):
        doc = super(OB, self).to_rec()

        _d = explode(doc['target'])
        # body object not serializable to MongoDB
        del _d['body']
        doc['target'] = _d
        doc['inscfg'] = explode(doc['inscfg'])
        doc['telcfg'] = explode(doc['telcfg'])
        doc['envcfg'] = explode(doc['envcfg'])
        doc['program'] = self.program.proposal

        if ('calib_tgtcfg' in doc and doc['calib_tgtcfg'] is not None and
            not isinstance(doc['calib_tgtcfg'], str)):
            _d = explode(doc['calib_tgtcfg'])
            del _d['body']
            doc['calib_tgtcfg'] = _d

        if ('calib_inscfg' in doc and doc['calib_inscfg'] is not None and
            not isinstance(doc['calib_inscfg'], str)):
            doc['calib_inscfg'] = explode(doc['calib_inscfg'])

        return doc

    def __repr__(self):
        return self.id

    __str__ = __repr__


class BaseTarget(object):
    pass

class StaticTarget(BaseTarget):
    def __init__(self, name=None, ra=None, dec=None, equinox=2000.0,
                 comment=''):
        super(StaticTarget, self).__init__()
        self.name = name
        self.ra, self.dec = normalize_radec_str(ra, dec)
        self.equinox = equinox
        self.comment = comment

        if self.ra is not None:
            self._recalc_body()

    def _recalc_body(self):
        self.body = Body(self.name, self.ra, self.dec, self.equinox)

    def import_record(self, rec):
        code = rec.get('code', '').strip()
        self.name = rec['name']
        self.ra, self.dec = normalize_radec_str(rec['ra'], rec['dec'])

        if 'equinox' in rec:
            self.equinox = int(rec['equinox'])
        else:
            # transform equinox, e.g. "J2000" -> 2000
            eq = rec['eq']
            if isinstance(eq, str):
                eq = eq.upper()
                if eq[0] in ('B', 'J'):
                    eq = eq[1:]
                    eq = float(eq)
            eq = int(eq)
            self.equinox = eq

        self.comment = rec['comment'].strip()

        self._recalc_body()
        return code

    def calc(self, observer, time_start):
        return self.body.calc(observer, time_start)


class HSCTarget(StaticTarget):
    def __init__(self, *args, **kwdargs):
        super(HSCTarget, self).__init__(*args, **kwdargs)


class TelescopeConfiguration(object):

    def __init__(self, focus=None, dome=None, comment=''):
        super(TelescopeConfiguration, self).__init__()
        self.focus = focus
        if dome is None:
            dome = 'open'
        else:
            dome = dome.lower()
        self.dome = dome
        self.min_el = 15.0
        self.max_el = 89.0
        self.comment = comment

    def get_el_minmax(self):
        return (self.min_el, self.max_el)

    def import_record(self, rec):
        code = rec.get('code', '').strip()
        self.focus = rec['focus'].upper()
        self.dome = rec['dome'].lower()
        self.comment = rec['comment'].strip()
        return code

class InstrumentConfiguration(object):

    def __init__(self):
        super(InstrumentConfiguration, self).__init__()

        self.insname = None
        self.mode = None
        self.comment = ''

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
        if dith2 is None:
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
                 dith1=60, dith2=None, skip=0, stop=None, comment=''):
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
        if dith2 is None:
            # TODO: defaults for this depends on mode
            dith2 = 0
        self.dith2 = dith2
        self.skip = skip
        if stop is None:
            stop = num_exp
        self.stop = stop
        self.comment = comment

    def calc_filter_change_time(self):
        # TODO: this needs to become more accurate
        filter_change_time_sec = 35.0 * 60.0
        return filter_change_time_sec

    def import_record(self, rec):
        code = rec.get('code', '').strip()
        self.insname = 'HSC'
        self.filter = rec['filter'].lower()
        self.mode = rec['mode']
        self.dither = rec['dither']
        if isinstance(rec['guiding'], bool):
            self.guiding = rec['guiding']
        else:
            self.guiding = rec['guiding'] in ('y', 'Y', 'yes', 'YES')
        self.num_exp = int(rec['num_exp'])
        self.exp_time = float(rec['exp_time'])
        self.pa = float(rec['pa'])
        self.offset_ra = float(rec['offset_ra'])
        self.offset_dec = float(rec['offset_dec'])
        self.dith1 = float(rec['dith1'])
        self.dith2 = float(rec['dith2'])
        self.skip = int(rec['skip'])
        self.stop = int(rec['stop'])
        self.comment = rec['comment'].strip()
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
        code = rec.get('code', '').strip()
        self.insname = 'FOCAS'
        self.mode = rec['mode']
        self.filter = rec['filter'].lower()
        if isinstance(rec['guiding'], bool):
            self.guiding = rec['guiding']
        else:
            self.guiding = rec['guiding'] in ('y', 'Y', 'yes', 'YES')
        self.num_exp = int(rec['num_exp'])
        self.exp_time = float(rec['exp_time'])
        self.pa = float(rec['pa'])
        self.offset_ra = float(rec['offset_ra'])
        self.offset_dec = float(rec['offset_dec'])
        self.dither_ra = float(rec['dither_ra'])
        self.dither_dec = float(rec['dither_dec'])
        self.dither_theta = float(rec['dither_theta'])
        self.binning = rec['binning']
        return code

class EnvironmentConfiguration(object):

    # Default time zone for lower_time_limit and upper_time_limit
    default_timezone = tz.UTC

    def __init__(self, seeing=None, airmass=None, moon='any',
                 transparency=None, moon_sep=None, lower_time_limit=None,
                 upper_time_limit=None, comment=''):
        super(EnvironmentConfiguration, self).__init__()
        self.seeing = seeing
        self.airmass = airmass
        self.transparency = transparency
        self.moon_sep = moon_sep
        if (moon is None) or (len(moon) == 0):
            moon = 'any'
        self.moon = moon.lower()
        self.lower_time_limit = lower_time_limit
        self.upper_time_limit = upper_time_limit
        self.comment = comment

    def import_record(self, rec):
        code = rec.get('code', '').strip()

        if isinstance(rec['seeing'], float):
            self.seeing = rec['seeing']
        else:
            seeing = rec['seeing'].strip()
            if len(seeing) != 0:
                self.seeing = float(seeing)
            else:
                self.seeing = None

        if isinstance(rec['airmass'], float):
            self.airmass = rec['airmass']
        else:
            airmass = rec['airmass'].strip()
            if len(airmass) != 0:
                self.airmass = float(airmass)
            else:
                self.airmass = None

        self.moon = rec['moon']
        self.moon_sep = float(rec['moon_sep'])
        self.transparency = float(rec['transparency'])
        if rec['lower_time_limit'] is None:
            self.lower_time_limit = None
        elif isinstance(rec['lower_time_limit'], datetime):
            # See NOTE [1]
            t = rec['lower_time_limit']
            self.lower_time_limit = t.replace(tzinfo=tz.UTC)
        else:
            try:
                self.lower_time_limit = parse_date_time(rec['lower_time_limit'],
                                                        self.default_timezone)
            except KeyError as e:
                self.lower_time_limit = None

        if rec['upper_time_limit'] is None:
            self.upper_time_limit = None
        elif isinstance(rec['upper_time_limit'], datetime):
            # See NOTE [1]
            t = rec['upper_time_limit']
            self.upper_time_limit = t.replace(tzinfo=tz.UTC)
        else:
            try:
                self.upper_time_limit = parse_date_time(rec['upper_time_limit'],
                                                        self.default_timezone)
            except KeyError as e:
                self.upper_time_limit = None

        self.comment = rec['comment'].strip()
        return code


class Executed_OB(PersistentEntity):
    """
    Describes the result of executing an OB.
    """
    def __init__(self, ob_key=None):
        super(Executed_OB, self).__init__('executed_ob')

        self.ob_key = ob_key
        # time this OB started and stopped
        self.time_start = None
        self.time_stop = None
        # list of exposure keys, one for each exposure
        self.exp_history = []
        self.iqa = ''
        self.fqa = ''
        # overall per OB-execution comment
        self.comment = ''

    @property
    def key(self):
        return dict(ob_key=self.ob_key, time_start=self.time_start)

    def add_exposure(self, exp_key):
        self.exp_history.append(exp_key)

    def from_rec(self, dct):
        super(Executed_OB, self).from_rec(dct)

        # comes in as a list from MongoDB, but we want a tuple
        self.ob_key = tuple(self.ob_key)

        # See NOTE [1]
        if self.time_start is not None:
            self.time_start = self.time_start.replace(tzinfo=tz.UTC)
        if self.time_stop is not None:
            self.time_stop = self.time_stop.replace(tzinfo=tz.UTC)

class HSC_Exposure(PersistentEntity):
    """
    Describes the result of executing one dither position or one exposure
    from an OB.
    """
    def __init__(self, ob_key=None, dithpos=None):
        super(HSC_Exposure, self).__init__('exposure')

        # time this exposure started and stopped
        self.time_start = None
        self.time_stop = None
        # per exposure comment
        self.comment = ''
        # exposure id that links a data frame with this OB
        self.exp_id = ''
        self.ob_key = ob_key

        # environment data at the time of exposure
        # TODO: should this end up being a list of tuples of measurements
        # taken at different times during the exposure
        self.transparency = None
        self.seeing = None
        self.moon_illumination = None
        self.moon_altitude = None
        self.moon_separation = None

        # Handling can be used to exclude certain exposures
        self.handling = 0
        self.dithpos = dithpos

        # Other items extracted from FITS header
        self.object_name = None
        self.filter_name = None
        self.data_type = None
        self.propid = None
        self.purpose = None
        self.obsmthd = None

    @property
    def key(self):
        return dict(exp_id=self.exp_id)

    def from_rec(self, dct):
        super(HSC_Exposure, self).from_rec(dct)

        # comes in as a list from MongoDB, but we want a tuple
        if self.ob_key is not None:
            # non-queue frames will have a null ob_key
            self.ob_key = tuple(self.ob_key)

        # See NOTE [1]
        if self.time_start is not None:
            self.time_start = self.time_start.replace(tzinfo=tz.UTC)
        if self.time_stop is not None:
            self.time_stop = self.time_stop.replace(tzinfo=tz.UTC)

    def __str__(self):
        return self.exp_id


class SavedStateRec(PersistentEntity):

    def __init__(self):
        super(SavedStateRec, self).__init__('saved_state')

        self.name = 'current'
        self.info = {}
        self.time_update = None

    def from_rec(self, dct):
        super(SavedStateRec, self).from_rec(dct)

        # See NOTE [1]
        if self.time_update is not None:
            self.time_update = self.time_update.replace(tzinfo=tz.UTC)

    @property
    def key(self):
        return dict(name='current')


def parse_date_time(dt_str, default_timezone):
    if len(dt_str) > 0:
        dt = dateutil.parser.parse(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_timezone)
    else:
        dt = None
    return dt

def normalize_radec_str(ra_str, dec_str):
    if ra_str is None or ra_str == '':
        ra = ra_str
    else:
        ra = wcs.raDegToString(wcs.hmsStrToDeg(ra_str))
    if dec_str is None or dec_str == '':
        dec = dec_str
    else:
        dec = wcs.decDegToString(wcs.dmsStrToDeg(dec_str))
    return (ra, dec)

#
### Functions for going from database record to Python object
###   (see q_query.py)
#
def make_program(dct):
    pgm = Program(dct['proposal'])
    pgm.from_rec(dct)
    return pgm

def make_executed_ob(dct):
    ex_ob = Executed_OB()
    ex_ob.from_rec(dct)
    return ex_ob

def make_exposure(dct):
    exp = HSC_Exposure()
    exp.from_rec(dct)
    return exp

def make_saved_state(dct):
    rec = SavedStateRec()
    rec.from_rec(dct)
    return rec

def make_ob(dct, program):

    telcfg = TelescopeConfiguration()
    telcfg.import_record(dct['telcfg'])

    target = HSCTarget()
    target.import_record(dct['target'])

    inscfg = HSCConfiguration()
    inscfg.import_record(dct['inscfg'])

    envcfg = EnvironmentConfiguration()
    envcfg.import_record(dct['envcfg'])

    if dct['calib_tgtcfg'] is None:
        # older programs didn't have this
        calib_tgtcfg = None
    else:
        calib_tgtcfg = HSCTarget()
        calib_tgtcfg.import_record(dct['calib_tgtcfg'])

    if dct['calib_inscfg'] is None:
        # older programs didn't have this
        calib_inscfg = None
    else:
        calib_inscfg = HSCConfiguration()
        calib_inscfg.import_record(dct['calib_inscfg'])

    # older programs didn't have this
    extra_params = dct.get('extra_params', '')

    ob = OB(id=dct['id'], program=program, target=target, telcfg=telcfg,
            inscfg=inscfg, envcfg=envcfg, calib_tgtcfg=calib_tgtcfg,
            calib_inscfg=calib_inscfg, total_time=dct['total_time'],
            acct_time=dct['acct_time'], priority=dct['priority'],
            name=dct['name'], comment=dct['comment'],
            extra_params=extra_params)
    ob._id = dct['_id']
    ob._save_tstamp = dct.get('_save_tstamp', None)

    return ob


#END
