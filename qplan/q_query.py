#
# Eric Jeschke (eric@naoj.org)
#

import datetime as dt

# MODULE FUNCTIONS

def get_ob_key(ob):
    """
    Return the key for an OB, given the OB.
    """
    proposal = ob.program.proposal.upper()
    ob_key = (proposal, ob.name)
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
        proposal = ob.program.proposal.upper()
        return proposal in propset
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

    def get_ob(self, ob_key):
        tbl = self._qa.get_table('ob')
        return tbl.find_one(dict(program=ob_key[0], name=ob_key[1]))

    def ob_keys_to_obs(self, ob_keys):
        return map(self.get_ob, ob_keys)

    def ex_ob_to_ob(self, ex_ob):
        """
        Return an OB, given a record for an executed OB.
        """
        return self.get_ob(ex_ob.ob_key)

    def map_ex_ob_to_ob(self, ex_obs):
        return map(self.ex_ob_to_ob, ex_obs)

    def get_exposures(self, executed_ob_rec):
        tbl = self._qa.get_table('exposure')
        return tbl.find({'exp_id': {'$in': executed_ob_rec.exp_history}})

    def get_program_by_semester(self, semester):
        """
        Get a program in semester.
            args: semester is list.   e.g. ['S16A', 'S16B']
        """
        semester = ["/^{}/".format(s.upper()[:4]) for s in semester]
        tbl = self._qa.get_table('program')
        return tbl.find({'exp_id': {'$in': executed_ob_rec.exp_history}})
        return filter(match_semester, tbl.values())

    def get_program_by_propid(self, propid):
        """
        Look up a program by propid.
        """
        tbl = self._qa.get_table('program')
        propid = propid.lower()
        for pgm in tbl.values():
            if pgm.propid == propid:
                return pgm
        raise NotFound("No program with propid '%s'" % (propid))

    def get_obs_by_proposal(self, proposal):
        """
        Get entire list of OBs from a proposal name.
        """
        res = []
        tbl = self._qa.get_table('ob')
        proposal = proposal.upper()
        for obkey in tbl:
            (_proposal, obname) = obkey
            if proposal == _proposal:
                res.append(tbl[obkey])
        return res

    def get_executed_obs_by_proposal(self, proposal):
        """
        Get executed OBs from a proposal name.
        """
        tbl = self._qa.get_table('executed_ob')
        proposal = proposal.upper()
        def has_proposal(rec):
            ob = self.get_ob(rec.ob_key)
            return ob.program.proposal == proposal
        return filter(has_proposal, tbl.values())

    def get_exposures_by_date(self, fromdate, todate):
        """
        Get exposure by date.
        """
        tbl = self._qa.get_table('exposure')
        def within_range(rec):
            if isinstance(rec.time_start, dt.datetime):
                return todate > rec.time_start >= fromdate
        return filter(within_range, tbl.values())

    def get_executed_obs_by_date(self, fromdate, todate):
        """
        Get executed OBs by date.
        """
        tbl = self._qa.get_table('executed_ob')
        def within_range(rec):
            return todate > rec.time_start >= fromdate
        return filter(within_range, tbl.values())

    ## def get_exposures_from_executed_obs(self, ex_obs):
    ##     """
    ##     Given a sequence of executed OBs, return the exposures for them.
    ##     """
    ##     tbl = self._qa.get_table('exposure')
    ##     return filter(within_range, tbl.values())

    def get_ob_count(self, ob_key):
        """
        Get the count of how many times an OB has been executed.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_match(rec):
            return rec.ob_key == ob_key
        return len(list(filter(ob_match, tbl.values())))


    def get_finalized_executed_obs(self, fqa_set):
        """
        Get the OBs that have been executed with a complete FQA.
        `fqa_set` should be a set with some combination of 'good' and
        'bad'.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_finished(rec):
            return rec.fqa in fqa_set
        return filter(ob_finished, tbl.values())

    def get_do_not_execute_ob_keys(self):
        """
        Get the keys for OBs that should not be executed because they are
        either FQA==good or have an IQA==good/marginal.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_match(rec):
            return (rec.fqa == 'good') or (rec.fqa == '' and
                                           rec.iqa in ('good', 'marginal'))

        #return self.map_ex_ob_to_ob(filter(ob_match, tbl.values()))
        return map(lambda rec: rec.ob_key,
                              filter(ob_match, tbl.values()))

    def get_schedulable_ob_keys(self):
        """
        Get the keys for OBs that can be scheduled, because their IQA/FQA enables
        that.
        """
        do_not_execute = set(self.get_do_not_execute_ob_keys())
        tbl = self._qa.get_table('ob')
        def ob_match(ob):
            return ob not in do_not_execute
        return filter(ob_match, tbl.values())


    def get_executed_obs_for_fqa(self):
        """
        Get the executed OB records that have IQA in (good, marginal) but
        no FQA==good
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_match(rec):
            return (rec.fqa != 'good') and (rec.iqa in ('good', 'marginal'))
        return filter(ob_match, tbl.values())

    def divide_executed_obs_by_program(self, ex_obs):
        """
        Given a list of executed ob records, returns a mapping of
        proposal names to lists of executed ob records
        """
        res = {}
        for rec in ex_obs:
            ob = self.get_ob(rec.ob_key)
            key = ob.program.proposal
            l = res.setdefault(key, [])
            l.append(rec)
        return res



#END
