#
# entity.py -- various entities used by queue system
#
#  E. Jeschke
#
from datetime import timedelta, datetime
import math
import dateutil.parser
from dateutil import tz

# 3rd party imports
import numpy as np
from astropy.coordinates import Angle
from astropy import units

entity_version = 20230109.0

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
        super().__init__()
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
                 skip=False, qc_priority=0.0):
        super().__init__('program')

        self.proposal = proposal
        if propid is None:
            # TODO: is there an algorithm to turn proposals
            # into propids?
            propid = proposal
        self.propid = propid
        self.pi = pi
        self.observers = observers
        self.rank = rank
        self.qc_priority = qc_priority
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

    def equivalent(self, other):
        if self.proposal != other.proposal:
            return False
        if self.propid != other.propid:
            return False
        if self.pi != other.pi:
            return False
        if self.observers != other.observers:
            return False
        if not np.isclose(self.rank, other.rank):
            return False
        if not np.isclose(self.qc_priority, other.qc_priority):
            return False
        if self.grade != other.grade:
            return False
        if self.partner != other.partner:
            return False
        if self.category != other.category:
            return False
        if not np.isclose(self.rank, other.rank):
            return False
        if set(self.instruments) != set(other.instruments):
            return False
        return True


class SlotError(Exception):
    pass

class Slot(object):
    """
    Slot -- a period of the night that can be scheduled.
    Defined by a start time and a duration in seconds.
    """

    def __init__(self, start_time, slot_len_sec, data=None):
        super().__init__()
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

    def printed(self):
        ob_s = "none" if self.ob is None else self.ob.printed()
        return "{} {}".format(self, ob_s)

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
        super().__init__()
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

    def printed(self):
        sch = []
        for slot in self.slots:
            sch.append(slot.printed())
        return "\n".join(sch)

    def __getitem__(self, index):
        return self.slots[index]

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
                 inscfg=None, envcfg=None, total_time=None, acct_time=None,
                 priority=1.0, derived=None, comment=''):
        super().__init__('ob')

        if id is None:
            id = "ob%d" % (OB.count)
            OB.count += 1
        self.id = id
        self.name = id

        # this plus the id make up the primary key of an OB
        self.program = program

        # constraints
        self.target = target
        self.inscfg = inscfg
        self.telcfg = telcfg
        self.envcfg = envcfg

        # other fields
        self.priority = priority
        self.acct_time = acct_time
        self.total_time = total_time
        self.derived = derived
        self.comment = comment

    @property
    def key(self):
        return dict(program=self.program.proposal, name=self.name)

    def has_calib(self):
        return False

    def to_rec(self):
        doc = super().to_rec()

        _d = explode(doc['target'])
        # body object not serializable to MongoDB
        del _d['body']
        doc['target'] = _d
        doc['inscfg'] = explode(doc['inscfg'])
        doc['telcfg'] = explode(doc['telcfg'])
        doc['envcfg'] = explode(doc['envcfg'])
        doc['program'] = self.program.proposal

        return doc

    def __repr__(self):
        return self.id

    def __str__(self):
        return self.id

    def printed(self):
        return "{} ({})".format(self.id, self.comment)

    def equivalent(self, other):
        if self.id != other.id:
            return False
        if not np.isclose(self.priority, other.priority):
            return False
        if not np.isclose(self.total_time, other.total_time):
            return False
        if not np.isclose(self.acct_time, other.acct_time):
            return False
        if self.derived != other.derived:
            return False
        if self.comment != other.comment:
            return False

        # costly object compares
        if not self.program.equivalent(other.program):
            return False
        if not self.target.equivalent(other.target):
            return False
        if not self.inscfg.equivalent(other.inscfg):
            return False
        if not self.telcfg.equivalent(other.telcfg):
            return False
        if not self.envcfg.equivalent(other.envcfg):
            return False

        return True

    def longslew_ob(self, prev_ob, total_time):
        if prev_ob is None:
            klass = self.inscfg.__class__
            inscfg = klass()
        else:
            #inscfg = prev_ob.inscfg
            inscfg = self.inscfg
        new_ob = OB(program=self.program, target=self.target,
                    telcfg=self.telcfg,
                    inscfg=inscfg, envcfg=self.envcfg,
                    total_time=total_time, derived=True,
                    comment="Long slew for {}".format(self))
        return new_ob

    def delay_ob(self, total_time):
        new_ob = OB(program=self.program, target=self.target,
                    telcfg=self.telcfg,
                    inscfg=self.inscfg, envcfg=self.envcfg,
                    total_time=total_time, derived=True,
                    comment="Delay for {} visibility".format(self))
        return new_ob


class HSC_OB(OB):
    """
    HSC Observing Block
    Defines an item that can be scheduled during the night for HSC.

    """
    def __init__(self, id=None, program=None, target=None, telcfg=None,
                 inscfg=None, envcfg=None, calib_tgtcfg=None,
                 calib_inscfg=None, total_time=None, acct_time=None,
                 priority=1.0, name=None, derived=None, comment='',
                 extra_params=''):
        super().__init__(id=id, program=program, target=target,
                         telcfg=telcfg, inscfg=inscfg, envcfg=envcfg,
                         total_time=total_time, acct_time=acct_time,
                         priority=priority, derived=derived, comment=comment)
        self.kind = 'hsc_ob'

        if name is None:
            name = self.id
        self.name = name

        # this can be None, "default" or a valid target configuration
        if isinstance(calib_tgtcfg, str) and calib_tgtcfg == 'default':
            # default calib_tgtcfg is same pointing as science target,
            # but name is prefixed with "calib for "
            calib_tgtcfg = HSCTarget(name="calib for %s" % target.name,
                                     ra=target.ra, dec=target.dec,
                                     equinox=target.equinox)
        self.calib_tgtcfg = calib_tgtcfg

        if isinstance(calib_inscfg, str) and calib_inscfg == 'default':
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
        self.extra_params = extra_params

    def has_calib(self):
        return True

    def to_rec(self):
        doc = super().to_rec()

        if ('calib_tgtcfg' in doc and doc['calib_tgtcfg'] is not None and
            not isinstance(doc['calib_tgtcfg'], str)):
            _d = explode(doc['calib_tgtcfg'])
            del _d['body']
            doc['calib_tgtcfg'] = _d

        if ('calib_inscfg' in doc and doc['calib_inscfg'] is not None and
            not isinstance(doc['calib_inscfg'], str)):
            doc['calib_inscfg'] = explode(doc['calib_inscfg'])

        return doc

    def equivalent(self, other):
        if not super().equivalent(other):
            return False
        if self.name != other.name:
            return False
        if self.extra_params != other.extra_params:
            return False

        # costly object compares
        if self.calib_tgtcfg is None:
            if other.calib_tgtcfg is not None:
                return False
        else:
            if other.calib_tgtcfg is None:
                return False
            elif not self.calib_tgtcfg.equivalent(other.calib_tgtcfg):
                return False

        if self.calib_inscfg is None:
            if other.calib_inscfg is not None:
                return False
        else:
            if other.calib_inscfg is None:
                return False
            elif not self.calib_inscfg.equivalent(other.calib_inscfg):
                return False

        return True

    def setup_time(self):
        # how long approx to start OB
        total_time = 1.0
        return total_time

    def setup_ob(self):
        d = dict(obid=str(self), obname=self.name,
                 comment=self.comment,    # root OB's comment
                 proposal=self.program.proposal)
        # make this derived OB's comment include root OB comment
        comment = "%(proposal)s %(obname)s: %(comment)s" % d

        # how long approx to start OB
        ob_change_sec = self.setup_time()

        new_ob = HSC_OB(program=self.program, target=self.target,
                        telcfg=self.telcfg,
                        inscfg=self.inscfg, envcfg=self.envcfg,
                        total_time=ob_change_sec, derived=True,
                        comment="Setup OB: %s" % (comment))
        # retain a reference to the original OB (is this still used anywhere?)
        new_ob.orig_ob = self
        return new_ob

    def teardown_time(self):
        # how long approx to stop current OB
        total_time = 1.0
        return total_time

    def teardown_ob(self):
        # how long approx to stop current OB
        ob_stop_sec = self.teardown_time()
        new_ob = HSC_OB(program=self.program, target=self.target,
                        telcfg=self.telcfg,
                        inscfg=self.inscfg, envcfg=self.envcfg,
                        total_time=ob_stop_sec, derived=True,
                        comment="Teardown for {}".format(self))
        return new_ob

    def filterchange_ob(self, total_time):
        new_ob = HSC_OB(program=self.program, target=self.target,
                        telcfg=self.telcfg,
                        inscfg=self.inscfg, envcfg=self.envcfg,
                        total_time=total_time, derived=True,
                        comment="Filter change for {}".format(self))
        return new_ob

    def calibration_ob(self, total_time):
        new_ob = HSC_OB(program=self.program, target=self.calib_tgtcfg,
                        telcfg=self.telcfg, inscfg=self.calib_inscfg,
                        envcfg=self.envcfg,
                        total_time=total_time, derived=True,
                        #extra_params=self.extra_params,
                        comment="Calibration for {}".format(self))
        return new_ob

    def calibration30_ob(self, total_time):
        calib_inscfg = HSCConfiguration(filter=self.inscfg.filter,
                                        guiding=False, num_exp=1,
                                        exp_time=30,
                                        mode='IMAGE', dither='1',
                                        pa=self.inscfg.pa,
                                        comment='30 sec calib shot')
        new_ob = HSC_OB(program=self.program, target=self.target,
                        telcfg=self.telcfg, inscfg=calib_inscfg,
                        envcfg=self.envcfg,
                        total_time=total_time, derived=True,
                        #extra_params=self.extra_params,
                        comment="30 sec calibration for {}".format(self))
        return new_ob


class PPC_OB(OB):
    """
    Observing Block for PFS Pointing Centers
    Defines an item that can be scheduled during the night.

    """
    def __init__(self, id=None, program=None, target=None, telcfg=None,
                 inscfg=None, envcfg=None, total_time=None, acct_time=None,
                 priority=1.0, derived=None, comment=''):
        super().__init__(id=id, program=program, target=target,
                         telcfg=telcfg, inscfg=inscfg, envcfg=envcfg,
                         total_time=total_time, acct_time=acct_time,
                         priority=priority, derived=derived, comment=comment)
        self.kind = 'ppc_ob'
        self.name = id

    def setup_time(self):
        # how long approx to start OB
        # 10 min for PFS fiber config?
        total_time = 10.0 * 60.0
        return total_time

    def setup_ob(self):
        d = dict(obid=str(self), obname=self.name,
                 comment=self.comment,    # root OB's comment
                 proposal=self.program.proposal)
        # make this derived OB's comment include root OB comment
        comment = "%(proposal)s %(obname)s: %(comment)s" % d

        # how long approx to start OB
        total_time = self.setup_time()

        new_ob = PPC_OB(program=self.program, target=self.target,
                        telcfg=self.telcfg,
                        inscfg=self.inscfg, envcfg=self.envcfg,
                        total_time=total_time, derived=True,
                        comment="Setup OB: %s" % (comment))
        #
        new_ob.orig_ob = self
        return new_ob

    def teardown_time(self):
        # how long approx to stop current OB
        total_time = 1.0
        return total_time

    def teardown_ob(self):
        # how long approx to stop current OB
        total_time = self.teardown_time()
        new_ob = PPC_OB(program=self.program, target=self.target,
                        telcfg=self.telcfg,
                        inscfg=self.inscfg, envcfg=self.envcfg,
                        total_time=total_time, derived=True,
                        comment="Teardown for {}".format(self))
        return new_ob


class PFS_OB(OB):
    """
    Observing Block for PFS
    Defines an target and parameters for observing it.

    """
    def __init__(self, id=None, program=None, target=None, telcfg=None,
                 inscfg=None, envcfg=None, total_time=None, acct_time=None,
                 priority=1.0, comment=''):
        super().__init__(id=id, program=program, target=target,
                         telcfg=telcfg, inscfg=inscfg, envcfg=envcfg,
                         total_time=total_time, acct_time=acct_time,
                         priority=priority, derived=None, comment=comment)
        self.kind = 'pfs_ob'
        self.name = id


class BaseTarget(object):
    pass

class StaticTarget(BaseTarget):
    def __init__(self, name=None, ra=None, dec=None, equinox=2000.0,
                 comment=''):
        super().__init__()
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

    def equivalent(self, other):
        if self.name != other.name:
            return False
        if self.ra != other.ra:
            return False
        if self.dec != other.dec:
            return False
        if self.equinox != other.equinox:
            return False
        if self.comment != other.comment:
            return False
        return True


class HSCTarget(StaticTarget):
    def __init__(self, *args, **kwdargs):
        super().__init__(*args, **kwdargs)


class TelescopeConfiguration(object):

    def __init__(self, focus=None, dome=None, comment=''):
        super().__init__()
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

    def equivalent(self, other):
        if self.focus != other.focus:
            return False
        if self.dome != other.dome:
            return False
        if not np.isclose(self.min_el, other.min_el):
            return False
        if not np.isclose(self.max_el, other.max_el):
            return False
        if self.comment != other.comment:
            return False
        return True


class InstrumentConfiguration(object):

    def __init__(self):
        super().__init__()

        self.insname = None
        self.mode = None
        self.comment = ''


class HSCConfiguration(InstrumentConfiguration):

    def __init__(self, filter=None, guiding=False, num_exp=1, exp_time=10,
                 mode='IMAGE', dither=1, offset_ra=0, offset_dec=0, pa=90,
                 dith1=60, dith2=None, skip=0, stop=None, comment=''):
        super().__init__()

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

    def check_filter_installed(self, installed_filters):
        return self.filter in installed_filters

    def calc_num_exp(self):
        num_exp = self.num_exp - (self.num_exp - self.stop) - self.skip
        return num_exp

    def calc_on_src_time(self):
        num_exp = self.calc_num_exp()
        return num_exp * self.exp_time

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

    def equivalent(self, other):
        if self.insname != other.insname:
            return False
        if self.mode != other.mode:
            return False
        if self.filter != other.filter:
            return False
        if self.dither != other.dither:
            return False
        if self.guiding != other.guiding:
            return False
        if self.num_exp != other.num_exp:
            return False
        if not np.isclose(self.exp_time, other.exp_time):
            return False
        if not np.isclose(self.offset_ra, other.offset_ra):
            return False
        if not np.isclose(self.offset_dec, other.offset_dec):
            return False
        if not np.isclose(self.pa, other.pa):
            return False
        if not np.isclose(self.dith1, other.dith1):
            return False
        if not np.isclose(self.dith2, other.dith2):
            return False
        if self.skip != other.skip:
            return False
        if self.stop != other.stop:
            return False
        if self.comment != other.comment:
            return False
        return True


class PPCConfiguration(InstrumentConfiguration):
    """PFS Pointing Center Instrument Configuration"""

    def __init__(self, exp_time=15, resolution='low',
                 guiding=True, pa=0, comment=''):
        super().__init__()

        self.insname = 'PPC'
        self.mode = 'SPEC'
        self.resolution = resolution
        self.guiding = guiding
        self.exp_time = float(exp_time)
        self.num_exp = 1
        self.pa = pa
        self.comment = comment

    def calc_filter_change_time(self):
        return 0.0

    def check_filter_installed(self, installed_filters):
        return True

    def calc_num_exp(self):
        return self.num_exp

    def import_record(self, rec):
        code = rec.get('code', '').strip()
        self.insname = 'PFS'
        self.resolution = rec['resolution']
        if isinstance(rec['guiding'], bool):
            self.guiding = rec['guiding']
        else:
            self.guiding = rec['guiding'] in ('y', 'Y', 'yes', 'YES')
        self.exp_time = float(rec['exp_time'])
        self.pa = float(rec['pa'])
        self.comment = rec['comment'].strip()
        return code

    def equivalent(self, other):
        if self.insname != other.insname:
            return False
        if self.resolution != other.resolution:
            return False
        if self.guiding != other.guiding:
            return False
        if not np.isclose(self.exp_time, other.exp_time):
            return False
        if not np.isclose(self.pa, other.pa):
            return False
        if self.comment != other.comment:
            return False
        return True


class PFSConfiguration(InstrumentConfiguration):
    """PFS Observing Block Instrument Configuration"""

    def __init__(self, exp_time=15, resolution='low',
                 comment=''):
        super().__init__()

        self.insname = 'PFS'
        self.mode = 'SPEC'
        self.resolution = resolution
        self.exp_time = float(exp_time)
        self.num_exp = 1
        self.comment = comment

    # These two shouldn't be needed because we never schedule PFS OBs
    # directly; it is done through the PPP program to get pointing centers

    def calc_filter_change_time(self):
        raise Exception("Not valid for a PFS OB")

    def check_filter_installed(self, installed_filters):
        raise Exception("Not valid for a PFS OB")

    def calc_num_exp(self):
        return self.num_exp

    def import_record(self, rec):
        code = rec.get('code', '').strip()
        self.insname = 'PFS'
        self.resolution = rec['resolution']
        self.exp_time = float(rec['exp_time'])
        self.comment = rec['comment'].strip()
        return code

    def equivalent(self, other):
        if self.insname != other.insname:
            return False
        if self.resolution != other.resolution:
            return False
        if not np.isclose(self.exp_time, other.exp_time):
            return False
        if self.comment != other.comment:
            return False
        return True


class EnvironmentConfiguration(object):

    # Default time zone for lower_time_limit and upper_time_limit
    default_timezone = tz.UTC

    def __init__(self, seeing=None, airmass=None, moon='any',
                 transparency=None, moon_sep=None, lower_time_limit=None,
                 upper_time_limit=None, comment=''):
        super().__init__()
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

    def equivalent(self, other):
        if not np.isclose(self.seeing, other.seeing):
            return False
        if not np.isclose(self.airmass, other.airmass):
            return False
        if self.moon != other.moon:
            return False
        if not np.isclose(self.moon_sep, other.moon_sep):
            return False
        if not np.isclose(self.transparency, other.transparency):
            return False
        if self.lower_time_limit != other.lower_time_limit:
            return False
        if self.upper_time_limit != other.upper_time_limit:
            return False
        if self.comment != other.comment:
            return False
        return True


class Executed_OB(PersistentEntity):
    """
    Describes the result of executing an OB.
    """
    def __init__(self, ob_key=None):
        super().__init__('executed_ob')

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
        super().from_rec(dct)

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
    from a HSC OB.
    """
    def __init__(self, ob_key=None, dithpos=None):
        super().__init__('exposure')
        self.insname = 'HSC'

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
        super().from_rec(dct)

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


class PFS_Exposure(PersistentEntity):
    """
    Describes the result of executing one exposure from a PFS OB.
    """
    def __init__(self, ob_key=None):
        super().__init__('exposure')
        self.insname = 'PFS'

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
        # taken at different times during the exposure?
        self.transparency = None
        self.seeing = None
        self.moon_illumination = None
        self.moon_altitude = None
        self.moon_separation = None

        # Handling can be used to exclude certain exposures
        self.handling = 0

        # Other items extracted from FITS header
        self.object_name = None
        self.resolution = None
        self.data_type = None
        self.propid = None
        self.obsmthd = None

    @property
    def key(self):
        return dict(exp_id=self.exp_id)

    def from_rec(self, dct):
        super().from_rec(dct)

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
        super().__init__('saved_state')

        self.name = 'current'
        self.info = {}
        self.time_update = None

    def from_rec(self, dct):
        super().from_rec(dct)

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
        # If ra is a float, assume that the angle is expressed in
        # decimal degrees. Otherwise, parse ra as a sexagesimal value,
        # i.e., HH:MM:SS.fff.
        if isinstance(ra_str, str) and ':' in ra_str:
            ra_ang = Angle(ra_str, unit=units.hour)
        else:
            ra_ang = Angle(float(ra_str), unit=units.deg)

        ra = ra_ang.to_string(unit=units.hour, sep=':', precision=3, pad=True)

    if dec_str is None or dec_str == '':
        dec = dec_str
    else:
        if isinstance(dec_str, str) and ':' in dec_str:
            dec_ang = Angle(dec_str, unit=units.deg)
        else:
            dec_ang = Angle(float(dec_str), unit=units.deg)

        dec = dec_ang.to_string(sep=':', precision=2, pad=True,
                                alwayssign=True)
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
    insname = dct.get('insname', None)
    if insname == 'PFS':
        exp = PFS_Exposure()
    else:
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

    envcfg = EnvironmentConfiguration()
    envcfg.import_record(dct['envcfg'])

    insname = dct['inscfg']['insname']

    if insname == 'HSC':
        target = HSCTarget()
        inscfg = HSCConfiguration()

        target.import_record(dct['target'])
        inscfg.import_record(dct['inscfg'])

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

        ob = HSC_OB(id=dct['id'], program=program, target=target,
                    telcfg=telcfg, inscfg=inscfg, envcfg=envcfg,
                    calib_tgtcfg=calib_tgtcfg, name=dct['name'],
                    calib_inscfg=calib_inscfg,
                    total_time=dct['total_time'], acct_time=dct['acct_time'],
                    priority=dct['priority'],
                    comment=dct['comment'],
                    extra_params=extra_params)

    elif insname == 'PPC':
        target = StaticTarget()
        inscfg = PPCConfiguration()

        target.import_record(dct['target'])
        inscfg.import_record(dct['inscfg'])

        ob = PPC_OB(id=dct['id'], program=program, target=target,
                    telcfg=telcfg, inscfg=inscfg, envcfg=envcfg,
                    total_time=dct['total_time'], acct_time=dct['acct_time'],
                    priority=dct['priority'], comment=dct['comment'])

    elif insname == 'PFS':
        target = StaticTarget()
        inscfg = PFSConfiguration()

        target.import_record(dct['target'])
        inscfg.import_record(dct['inscfg'])

        ob = PFS_OB(id=dct['id'], program=program, target=target,
                    telcfg=telcfg, inscfg=inscfg, envcfg=envcfg,
                    total_time=dct['total_time'], acct_time=dct['acct_time'],
                    priority=dct['priority'], comment=dct['comment'])

    else:
        raise ValueError(f"instrument not recognized: '{insname}'")

    ob._id = dct['_id']
    ob._save_tstamp = dct.get('_save_tstamp', None)

    return ob


#END
