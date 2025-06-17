#
#  E. Jeschke
#
from dateutil import tz

from ginga.misc.Bunch import Bunch

from qplan import entity
from qplan.util import dates

# MODULE FUNCTIONS

def get_ob_key(ob):
    """
    Return the key for an OB, given the OB.
    """
    ob_key = (ob.program, ob.name)
    return ob_key

# FILTERS

def filter_ob_keys_by_props(ob_keys, propset):
    propset = set(propset)
    def has_proposal(key):
        return key[0] in propset
    return filter(has_proposal, ob_keys)

def filter_obs_by_props(obs, propset):
    propset = set(propset)
    def has_proposal(ob):
        return ob.program.proposal in propset
    return filter(has_proposal, obs)


# QUERIES

class QueryError(Exception):
    pass

class NotFound(QueryError):
    pass

class QueueQuery(object):
    """
    Class for doing common queries against the Queue database.

    qq = QueueQuery(da)
    """

    def __init__(self, qa, use_cache=True):
        self._qa = qa
        self.logger = qa.logger

        self.use_cache = use_cache
        self.cache = {}

    def get_ob(self, ob_key):
        if self.use_cache:
            try:
                return self.get_cache('ob', ob_key)
            except KeyError:
                pass

        tbl = self._qa.get_db_native_table('ob')
        rec = tbl.find_one(dict(program=ob_key[0], name=ob_key[1]))
        pgm = self.get_program(ob_key[0])
        ob = entity.make_ob(rec, pgm)

        if self.use_cache:
            self.add_cache('ob', ob_key, ob)

        return ob

    def _make_ob(self, ob_rec):
        pgm = self.get_program(ob_rec['program'])
        ob = entity.make_ob(ob_rec, pgm)
        return ob

    def _make_obs(self, ob_recs):
        return map(self._make_ob, ob_recs)

    def get_program(self, proposal):
        proposal = proposal.upper()
        return self.cmake1('program', proposal, {'proposal': proposal},
                           entity.make_program)

    def get_hsc_program_stats(self, proposal):
        proposal = proposal.upper()
        return self.cmake1('hsc_program_stats', proposal, {'proposal': proposal},
                           entity.make_hsc_program_stats)

    def get_pfs_program_stats(self, proposal):
        proposal = proposal.upper()
        return self.cmake1('pfs_program_stats', proposal, {'proposal': proposal},
                           entity.make_pfs_program_stats)

    def _ob_keys_to_obs(self, ob_keys):
        ob_map = self.partition_ob_keys_by_program(ob_keys)
        if len(ob_map) == 0:
            return []
        query = {'$or': [{'$and':[ {'program': proposal},
                                   {'name': {'$in': names}}
                                   ]}
                         for proposal, names in ob_map.items()
                         ]}
        tbl = self._qa.get_db_native_table('ob')
        return tbl.find(query)

    def ob_keys_to_obs(self, ob_keys):
        #return map(self.get_ob, ob_keys)
        recs = self._ob_keys_to_obs(ob_keys)
        return self._make_obs(recs)

    def ex_ob_to_ob(self, ex_ob):
        """
        Return an OB object, given an executed OB object.
        """
        return self.get_ob(ex_ob.ob_key)

    def map_ex_ob_to_ob(self, ex_obs):
        return map(self.ex_ob_to_ob, ex_obs)

    def get_exposure(self, exp_id):
        """
        Get a single exposure from an exposure id string.
        e.g. get_exposure('HSCA17876000')
        """
        exp_id = exp_id.upper()
        return self.cmake1('exposure', exp_id, {'exp_id': exp_id},
                           entity.make_exposure)

    def get_exposures(self, executed_ob):
        """
        Get exposures from an executed OB object.
        """
        tbl = self._qa.get_db_native_table('exposure')
        recs = tbl.find({'exp_id': {'$in': executed_ob.exp_history}})
        return self.cmake_iter('exposure', recs,
                               lambda rec: rec['exp_id'],
                               entity.make_exposure)

    def get_program_by_semester(self, semester):
        """
        Get a program in semester.
            args: semester is list.   e.g. ['S16A', 'S16B']
        """
        semester = ["^{}".format(s.upper()[:4]) for s in semester]
        tbl = self._qa.get_db_native_table('program')
        all_recs = []
        for sem in semester:
            all_recs.extend(list(tbl.find({'proposal': {'$regex': sem}})))
        return self.cmake_iter('program', all_recs,
                               lambda rec: rec['proposal'],
                               entity.make_program)

    def get_program_by_propid(self, propid):
        """
        Look up a program by propid.

        WARNING: aren't some old propid's reused for new programs?!!
        """
        tbl = self._qa.get_db_native_table('program')
        propid = propid.lower()
        try:
            rec = tbl.find_one(dict(propid=propid))
            return self.get_program(rec['proposal'])

        except Exception:
            raise NotFound("No program with propid '%s'" % (propid))

    def get_intensive_program_auxinfo(self):
        """
        Look up intensive program auxilliary information.
        """
        tbl = self._qa.get_db_native_table('intensive_program')
        all_recs = tbl.find()
        intensives = self.cmake_iter('intensive_program', all_recs,
                                     lambda rec: rec['proposal'],
                                     entity.make_intensive_program)
        return {str(i_pgm): i_pgm for i_pgm in intensives}

    def get_obs_by_proposal(self, proposal):
        """
        Get entire list of OBs from a proposal name.
        """
        proposal = proposal.upper()
        tbl = self._qa.get_db_native_table('ob')
        recs = tbl.find(dict(program=proposal))
        return self._make_obs(recs)

    def get_executed_obs_by_proposal(self, proposal):
        """
        Get executed OBs from a proposal name.
        """
        proposal = proposal.upper()
        tbl = self._qa.get_db_native_table('executed_ob')
        recs = tbl.find({'ob_key.0': proposal})

        return self.cmake_iter('executed_ob', recs,
                               lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                               entity.make_executed_ob)

    def get_pfs_executed_ob_stats_by_proposal(self, proposal):
        """
        Get PFS executed OB Stats from a proposal name.
        """
        proposal = proposal.upper()
        tbl = self._qa.get_db_native_table('pfs_executed_ob_stats')
        recs = tbl.find({'ob_key.0': proposal})

        return self.cmake_iter('pfs_executed_ob_stats', recs,
                               lambda rec: tuple(rec['ob_key']),
                               entity.make_pfs_executed_ob_stats)

    def get_exposures_by_date(self, fromdate, todate):
        """
        Get exposure by date.
        """
        tbl = self._qa.get_db_native_table('exposure')
        recs = tbl.find({'$and': [{'time_start': {'$gte': fromdate}},
                                  {'time_stop': {'$lte': todate}}]})
        return self.cmake_iter('exposure', recs,
                               lambda rec: rec['exp_id'],
                               entity.make_exposure)

    def get_executed_obs_by_date(self, fromdate, todate, insname=None):
        """
        Get executed OBs by date.
        """
        tbl = self._qa.get_db_native_table('executed_ob')
        predicate = [{'time_start': {'$gte': fromdate}},
                     {'time_stop': {'$lte': todate}}]
        if insname is not None:
            predicate.append({'insname': insname})
        recs = tbl.find({'$and': predicate})
        return self.cmake_iter('executed_ob', recs,
                               lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                               entity.make_executed_ob)

    def get_executed_obs_by_ob_key(self, ob_key):
        """
        Get executed OBs by OB key.
        """
        tbl = self._qa.get_db_native_table('executed_ob')
        recs = tbl.find({'ob_key': ob_key})

        return self.cmake_iter('executed_ob', recs,
                               lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                               entity.make_executed_ob)

    def get_pfs_executed_ob_stats_by_ob_key(self, ob_key):
        """
        Get PFS executed OB stats by OB key.
        """
        return self.cmake1('pfs_executed_ob_stats', ob_key, {'ob_key': ob_key},
                           entity.make_pfs_executed_ob_stats)

    def get_exposures_from_executed_obs(self, ex_obs):
        """
        Given a sequence of executed OBs, return the exposures for them.
        """
        res = []
        for ex_ob in ex_obs:
            res.extend(list(self.get_exposures(ex_ob)))
        return res

    def get_ob_count(self, ob_key):
        """
        Get the count of how many times an OB has been executed.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_db_native_table('executed_ob')
        return tbl.count_documents(dict(ob_key=ob_key))

    def get_finalized_executed_obs(self, fqa_set, insname='HSC'):
        """
        Get the OBs that have been executed with a complete FQA.
        `fqa_set` should be a set with some combination of 'good' and
        'bad'.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_db_native_table('executed_ob')
        recs = tbl.find({'$and': [{'insname': insname},
                                  {'fqa': {'$in': fqa_set}}]})
        return self.cmake_iter('executed_ob', recs,
                               lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                               entity.make_executed_ob)

    def get_do_not_execute_ob_keys(self, insname='HSC'):
        """
        Get the keys for OBs that should not be executed because they are
        either FQA==good or have an IQA==good/marginal.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_db_native_table('executed_ob')
        recs = tbl.find({'$and': [{'insname': insname},
                                  {'$or':[ {'fqa': 'good'},
                                           {'$and': [{'fqa':''},
                                                     {'iqa':{'$in':['good',
                                                                    'marginal']}
                                                      }]}
                                          ]}]}, {'ob_key': 1})
        return [tuple(rec['ob_key']) for rec in recs]

    def get_do_not_execute_ob_info(self, proplst, tz_local):
        """
        Get the keys for OBs that should not be executed because they are
        either FQA==good or have an IQA==good/marginal.  `proplst` gives
        a set of proposals for which we want info.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_db_native_table('executed_ob')
        recs = tbl.find({'$and':[ {'ob_key.0': {'$in': proplst}},
                                  {'$or':[ {'fqa': 'good'},
                                           {'$and': [{'fqa':''},
                                                     {'iqa':{'$in':['good', 'marginal']}
                                                      }]}
                                           ]}
                                  ]}, {'ob_key': 1, 'time_start': 1})

        # Painful reconstruction of time already accumulated running the
        # programs for executed OBs.  Needed to inform scheduler so that
        # it can correctly calculate when to stop allocating OBs for a
        # program that has reached its time limit.
        recs = list(recs)
        dne_ob_keys = [tuple(rec['ob_key']) for rec in recs]
        props = {}
        ob_recs = self._ob_keys_to_obs(dne_ob_keys)
        for rec, ob_rec in zip(recs, ob_recs):
            proposal = ob_rec['program']
            if proposal in props:
                bnch = props[proposal]
            else:
                bnch = Bunch(obcount=0, sched_time=0.0)
                props[proposal] = bnch
            bnch.sched_time += ob_rec['acct_time']
            bnch.obcount += 1

            # record totals by semester as well as overall
            time_start = rec['time_start'].replace(tzinfo=tz.UTC)
            sem = dates.get_semester_by_datetime(time_start, tz_local)
            sem_time_key = f"sched_time_{sem}"
            sem_time = bnch.get(sem_time_key, 0.0)
            bnch[sem_time_key] = sem_time + ob_rec['acct_time']
            sem_count_key = f"obcount_{sem}"
            sem_count = bnch.get(sem_count_key, 0)
            bnch[sem_count_key] = sem_count + 1

        return dne_ob_keys, props

    def get_fqa_ob_info(self, proplst, tz_local):
        """
        Get the keys for OBs that have a finalized FQA.  `proplst` gives
        a set of proposals for which we want info.
        """
        tbl = self._qa.get_db_native_table('executed_ob')
        recs = tbl.find({'$and':[ {'ob_key.0': {'$in': proplst}},
                                  {'fqa': {'$in': ['good', 'bad']}},
                                  ]}, {'ob_key': 1, 'time_start': 1,
                                       'fqa': 1})

        recs = list(recs)
        fqa_ob_keys = [tuple(rec['ob_key']) for rec in recs]
        props = {}
        ob_recs = self._ob_keys_to_obs(fqa_ob_keys)
        for rec, ob_rec in zip(recs, ob_recs):
            proposal = ob_rec['program']
            if proposal in props:
                bnch = props[proposal]
            else:
                bnch = Bunch()
                props[proposal] = bnch

            # record totals by semester
            time_start = rec['time_start'].replace(tzinfo=tz.UTC)
            sem = dates.get_semester_by_datetime(time_start, tz_local)
            fqa = rec['fqa']
            sem_time_key = f"{fqa}_time_{sem}"
            sem_time = bnch.get(sem_time_key, 0.0)
            bnch[sem_time_key] = sem_time + ob_rec['acct_time']
            sem_count_key = f"{fqa}_obcount_{sem}"
            sem_count = bnch.get(sem_count_key, 0)
            bnch[sem_count_key] = sem_count + 1

        return fqa_ob_keys, props

    def get_schedulable_ob_keys(self, insname='HSC'):
        """
        Get the keys for OBs that can be scheduled, because their IQA/FQA
        enables that.
        """
        do_not_execute = set(self.get_do_not_execute_ob_keys(insname=insname))
        tbl = self._qa.get_db_native_table('ob')
        recs = tbl.find({'kind': insname.lower() + '_ob'},
                        {'program': 1, 'name': 1})
        all_obs = set([(rec['program'], rec['name']) for rec in recs])
        return all_obs - do_not_execute

    def get_executed_obs_for_fqa(self, insname='HSC'):
        """
        Get the executed OB records that have IQA in (good, marginal) but
        blank FQA
        """
        # Locate the executed_ob table
        tbl = self._qa.get_db_native_table('executed_ob')
        recs = tbl.find({'$and': [{'insname': insname},
                                  {'$and':[ {'fqa': {'$eq': ''}},
                                            {'iqa': {'$in':['good',
                                                            'marginal']}}
                                           ]}]})
        return self.cmake_iter('executed_ob', recs,
                               lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                               entity.make_executed_ob)

    def divide_executed_obs_by_program(self, ex_obs):
        """
        Given a list of executed ob records, returns a mapping of
        proposal names to lists of executed ob records
        """
        res = {}
        for ex_ob in ex_obs:
            ob = self.get_ob(ex_ob.ob_key)
            key = ob.program.proposal
            l = res.setdefault(key, [])
            l.append(ex_ob)
        return res

    def partition_ob_keys_by_program(self, ob_keys):
        """
        Given a list of executed ob records, returns a mapping of
        proposal names to lists of executed ob records
        """
        res = {}
        for ob_key in ob_keys:
            key = ob_key[0]
            l = res.setdefault(key, [])
            l.append(ob_key[1])
        return res

    #
    # cache management
    #
    def get_cache(self, tblname, key):
        subcache = self.cache.setdefault(tblname, {})
        return subcache[key]

    def add_cache(self, tblname, key, pyobj):
        subcache = self.cache.setdefault(tblname, {})
        subcache[key] = pyobj

    def clear_subcache(self, tblname):
        self.cache[tblname] = {}

    def clear_cache(self):
        self.cache = {}

    def cmake_iter(self, tblname, recs, key_fn, make_fn):
        """Look up objects corresponding to records (`recs`) in the cache
        with the subcache named `tblname`.
        `key_fn` is a function to apply to each record to get the keys for
        the objects.  If an object is found in the cache, use it; otherwise
        run `make_fn` on the record to create the object and cache it for
        future use.  A list of the objects is returned.
        """
        res = []
        for rec in recs:
            key = key_fn(rec)
            if self.use_cache:
                try:
                    pyobj = self.get_cache(tblname, key)
                    res.append(pyobj)
                    continue
                except KeyError:
                    pass

            pyobj = make_fn(rec)
            res.append(pyobj)
            if self.use_cache:
                self.add_cache(tblname, key, pyobj)
        return res

    def cmake1(self, tblname, key, query, make_fn):
        """Look up object under `key` in the subcache corresponding to
        `tblname`.  If found, return it, otherwise perform a singleton
        query (`query`) to locate a record in the db for the object and
        run `make_fn` on it to create the object.
        Object is cached for future use, then returned.
        """
        if self.use_cache:
            try:
                return self.get_cache(tblname, key)
            except KeyError:
                pass

        tbl = self._qa.get_db_native_table(tblname)
        rec = tbl.find_one(query)
        if rec is None:
            raise KeyError(key)
        pyobj = make_fn(rec)
        if self.use_cache:
            self.add_cache(tblname, key, pyobj)
        return pyobj
