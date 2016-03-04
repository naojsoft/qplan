#
# Eric Jeschke (eric@naoj.org)
#

import itertools

# MODULE FUNCTIONS

def get_ob_key(ob):
    """
    Return the key for an OB, given the OB.
    """
    proposal = ob.program.proposal.upper()
    ob_key = (proposal, ob.name)
    return ob_key

def filter_ob_keys_by_props(ob_keys, propset):
    propset = set(propset)
    def has_proposal(key):
        return key[0] in propset
    return itertools.ifilter(has_proposal, ob_keys)

def filter_obs_by_props(obs, propset):
    propset = set(propset)
    def has_proposal(ob):
        return ob.program.proposal in propset
    return itertools.ifilter(has_proposal, obs)


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
        return tbl[ob_key]

    def get_exposures(self, executed_ob_rec):
        tbl = self._qa.get_table('exposure')
        return itertools.imap(lambda exp_key: tbl[exp_key],
                              executed_ob_rec.exp_history)


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
        tbl = self._qa.get_table('ob')
        proposal = proposal.upper()
        for obkey in tbl:
            (_proposal, obname) = obkey
            if proposal == _proposal:
                yield tbl[obkey]

    def get_executed_obs_by_proposal(self, proposal):
        """
        Get executed OBs from a proposal name.
        """
        tbl = self._qa.get_table('executed_ob')
        proposal = proposal.upper()
        def has_proposal(rec):
            ob = self.get_ob(rec.ob_key)
            return ob.program.proposal == proposal
        return itertools.ifilter(has_proposal, tbl.values())

    def get_executed_obs_by_date(self, fromdate, todate):
        """
        Get executed OBs by date.
        """
        tbl = self._qa.get_table('executed_ob')
        def within_range(rec):
            return todate > rec.time_start >= fromdate
        return itertools.ifilter(within_range, tbl.values())

    def get_ob_count(self, ob_key):
        """
        Get the count of how many times an OB has been executed.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_match(rec):
            return rec.ob_key == ob_key
        return len(list(itertools.ifilter(ob_match, tbl.values())))


    def get_finalized_executed_obs(self):
        """
        Get the OBs that have been executed with a complete FQA.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_match(rec):
            if rec.fqa == 'good':
                return self.get_ob(rec.ob_key)
        return itertools.imap(ob_match, tbl.values())

    def get_do_not_execute_obs(self):
        """
        Get the list of OBs that should not be executed because they are
        either FQA==good or have an IQA==good/marginal.
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_match(rec):
            if (rec.fqa == 'good') or (rec.iqa in ('good', 'marginal')):
                return self.get_ob(rec.ob_key)
        return itertools.imap(ob_match, tbl.values())

    def get_schedulable_obs(self):
        """
        Get the OBs that can be scheduled, because their IQA/FQA enables
        that.
        """
        do_not_execute = set(self.get_do_not_execute_obs())
        tbl = self._qa.get_table('ob')
        def ob_match(ob):
            return ob not in do_not_execute
        return itertools.ifilter(ob_match, tbl.values())


    def get_executed_obs_for_fqa(self):
        """
        Get the executed OB records that have IQA in (good, marginal) but
        no FQA==good
        """
        # Locate the executed_ob table
        tbl = self._qa.get_table('executed_ob')
        def ob_match(rec):
            return (rec.fqa != 'good') and (rec.iqa in ('good', 'marginal'))
        return itertools.ifilter(ob_match, tbl.values())



#END
