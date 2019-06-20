#
# Eric Jeschke (eric@naoj.org)
#

from qplan import entity

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

    def __init__(self, qa):
        self._qa = qa
        self.logger = qa.logger

        self.use_cache = True
        self.cache = {}

    def get_ob(self, ob_key):
        if self.use_cache:
            try:
                return self.get_cache('ob', ob_key)
            except KeyError:
                pass

        tbl = self._qa.get_table('ob')
        rec = tbl.find_one(dict(program=ob_key[0], name=ob_key[1]))
        pgm = self.get_program(ob_key[0])
        ob = entity.make_ob(rec, pgm)

        if self.use_cache:
            self.add_cache('ob', ob_key, ob)

        return ob

    def _make_ob(self, ob_rec):
        obs = self._make_obs([ob_rec])
        return obs[0]

    def _make_obs(self, ob_recs):
        return self.get_or_make('ob', ob_recs,
                                lambda rec: (rec['program'], rec['name']),
                                entity.make_ob)

    def get_program(self, proposal):
        proposal = proposal.upper()
        if self.use_cache:
            try:
                return self.get_cache('program', proposal)
            except KeyError:
                pass

        tbl = self._qa.get_table('program')
        rec = tbl.find_one(dict(proposal=proposal))
        pgm = entity.make_program(rec)
        if self.use_cache:
            self.add_cache('program', proposal, pgm)

        return pgm

    def ob_keys_to_obs(self, ob_keys):
        # TODO: can this be made more efficient with a Mongo query?
        return map(self.get_ob, ob_keys)

    def ex_ob_to_ob(self, ex_ob):
        """
        Return an OB, given a record for an executed OB.
        """
        return self.get_ob(ex_ob.ob_key)

    def map_ex_ob_to_ob(self, ex_obs):
        return map(self.ex_ob_to_ob, ex_obs)

    def get_exposures(self, executed_ob):
        tbl = self._qa.get_table('exposure')
        recs = tbl.find({'exp_id': {'$in': executed_ob.exp_history}})
        return self.get_or_make('exposure', recs,
                                lambda rec: rec['exp_id'],
                                entity.make_exposure)

    def get_program_by_semester(self, semester):
        """
        Get a program in semester.
            args: semester is list.   e.g. ['S16A', 'S16B']
        """
        semester = ["^{}".format(s.upper()[:4]) for s in semester]
        tbl = self._qa.get_table('program')
        all_recs = []
        for sem in semester:
            all_recs.extend(list(tbl.find({'proposal': {'$regex': sem}})))
        return self.get_or_make('program', all_recs,
                                lambda rec: rec['proposal'],
                                entity.make_program)

    def get_program_by_propid(self, propid):
        """
        Look up a program by propid.

        WARNING: aren't some old propid's reused for new programs?!!
        """
        tbl = self._qa.get_table('program')
        propid = propid.lower()
        try:
            rec = tbl.find_one(dict(propid=propid))
            return self.get_program(rec['proposal'])

        except Exception:
            raise NotFound("No program with propid '%s'" % (propid))

    def get_obs_by_proposal(self, proposal):
        """
        Get entire list of OBs from a proposal name.
        """
        proposal = proposal.upper()
        tbl = self._qa.get_table('ob')
        recs = tbl.find(dict(program=proposal))
        return self._make_obs(recs)

    def get_executed_obs_by_proposal(self, proposal):
        """
        Get executed OBs from a proposal name.
        """
        proposal = proposal.upper()
        tbl = self._qa.get_table('executed_ob')
        recs = tbl.find({'ob_key.0': proposal})

        return self.get_or_make('executed_ob', recs,
                                lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                                entity.make_executed_ob)

    def get_exposures_by_date(self, fromdate, todate):
        """
        Get exposure by date.
        """
        tbl = self._qa.get_table('exposure')
        recs = tbl.find({'$and': [{'time_start': {'$gte': fromdate}},
                                  {'time_stop': {'$lte': todate}}]})
        return self.get_or_make('exposure', recs,
                                lambda rec: rec['exp_id'],
                                entity.make_exposure)

    def get_executed_obs_by_date(self, fromdate, todate):
        """
        Get executed OBs by date.
        """
        tbl = self._qa.get_table('executed_ob')
        recs = tbl.find({'$and': [{'time_start': {'$gte': fromdate}},
                                  {'time_stop': {'$lte': todate}}
                                  ]})
        return self.get_or_make('executed_ob', recs,
                                lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                                entity.make_executed_ob)

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
        tbl = self._qa.get_table('executed_ob')
        return tbl.count_documents(dict(ob_key=ob_key))

    def get_finalized_executed_obs(self, fqa_set):
        """
        Get the OBs that have been executed with a complete FQA.
        `fqa_set` should be a set with some combination of 'good' and
        'bad'.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        recs = tbl.find(dict(fqa={'$in': fqa_set}))
        return self.get_or_make('executed_ob', recs,
                                lambda rec: (tuple(rec['ob_key']), rec['time_start']),
                                entity.make_executed_ob)

    def get_do_not_execute_ob_keys(self):
        """
        Get the keys for OBs that should not be executed because they are
        either FQA==good or have an IQA==good/marginal.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        recs = tbl.find({'$or':[ {'fqa': 'good'},
                                 {'$and': [{'fqa':''},
                                           {'iqa':{'$in':['good', 'marginal']}
                                            }]}
                                 ]}, {'ob_key': 1})
        return [tuple(rec['ob_key']) for rec in recs]

    def get_schedulable_ob_keys(self):
        """
        Get the keys for OBs that can be scheduled, because their IQA/FQA
        enables that.
        """
        do_not_execute = set(self.get_do_not_execute_ob_keys())
        tbl = self._qa.get_table('ob')
        recs = tbl.find({}, {'program': 1, 'name': 1})
        all_obs = set([(rec['program'], rec['name']) for rec in recs])
        return all_obs - do_not_execute

    def get_executed_obs_for_fqa(self):
        """
        Get the executed OB records that have IQA in (good, marginal) but
        blank FQA
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        recs = tbl.find({'$and':[ {'fqa': {'$eq': ''}},
                                  {'iqa': {'$in':['good', 'marginal']}}
                                  ]})
        return self.get_or_make('executed_ob', recs,
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

    def get_or_make(self, tblname, recs, key_fn, make_fn):
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

#END
