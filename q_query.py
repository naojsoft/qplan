#
# Eric Jeschke (eric@naoj.org)
#

import itertools


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

    def get_program_by_propid(self, propid):
        """Look up a program by propid"""
        tbl = self._qa.get_table('program')
        propid = propid.lower()
        for pgm in tbl.values():
            if pgm.propid == propid:
                return pgm
        raise NotFound("No program with propid '%s'" % (propid))

    def get_obs_by_proposal(self, proposal):
        """Get entire list of OBs from a proposal name"""
        tbl = self._qa.get_table('ob')
        proposal = proposal.upper()
        for obkey in tbl:
            (_proposal, obname) = obkey
            if proposal == _proposal:
                yield tbl[obkey]

    def get_executed_obs_by_proposal(self, proposal):
        """Get executed OBs from a proposal name"""
        tbl = self._qa.get_table('executed_ob')
        proposal = proposal.upper()
        def has_proposal(rec):
            return rec.ob.program.proposal == proposal
        return itertools.ifilter(has_proposal, tbl.values())

    def get_executed_obs_by_date(self, fromdate, todate):
        """Get executed OBs by date"""
        tbl = self._qa.get_table('executed_ob')
        def within_range(rec):
            return todate > rec.time_start >= fromdate
        return itertools.ifilter(within_range, tbl.values())
