#!/usr/bin/env python

# Connect to the ProMS MySQL user database. Includes queries for ProMS
# ID and ProMS ID/password.

import os, sys
import MySQLdb
import sqlalchemy
import logging
from sqlsoup import SQLSoup as SqlSoup

from ginga.misc import log

class ProMSdbError(Exception):
    pass

class ProMSdb(object):
    def __init__(self,  logger=None, dblogger=False):
        super(ProMSdb, self).__init__()
        self.logger=logger
        if self.logger and dblogger:
            for h in self.logger.handlers:
                logging.getLogger('sqlalchemy.engine').setLevel(h.level)
                logging.getLogger('sqlalchemy.engine').addHandler(h)

        try:
            self.server = os.environ['PROMS_DB_SERVER']
            self.user   = os.environ['PROMS_DB_USER']
            self.passwd = os.environ['PROMS_DB_PASSWD']
            self.dbname = os.environ['PROMS_DB_DBNAME']
        except KeyError:
            raise ProMSdbError('ProMS DB connection information not found in environment variables')

        self.logger.info('PROMS_DB_SERVER is %s' % self.server)

        try:
            debug = os.environ['PROMS_DB_DEBUG']
            self.debug = True if debug.lower() == 'true' else False
        except KeyError:
            self.debug = False
        self.logger.info('debug is %s' % self.debug)

        engine = sqlalchemy.create_engine('mysql://', creator=self.getconn_mysqldb)
        self.db = SqlSoup(engine)
        try:
            self.auth = self.db.auth # "auth" table
        except MySQLdb.OperationalError as e:
            msg = 'Unexpected error while connecting to PROMS_DB_SERVER: %s' % e[1]
            self.logger.error(msg)
            raise ProMSdbError(msg)

    def getconn_mysqldb(self):
        c = MySQLdb.connect(self.server, self.user, self.passwd, self.dbname)
        return c

    def user_in_proms(self, id):
        try:
            # auth is table name
            res = self.auth.filter_by(email='%s' % id).first()
        except Exception as e:
            self.logger.error('Unexpected error while getting user information: %s %s' % (id, e))
            res = None

        return res

    def user_auth_in_proms(self, id, passwd):
        # Unless we are debugging this code, turn off "info" logging
        # for the query to avoid having the password being written to
        # the log file.
        savedLevel = logging.getLogger('sqlalchemy.engine').level
        if not self.debug:
            logging.getLogger('sqlalchemy.engine').setLevel(logging.WARN)
        try:
            # auth is table name
            res = self.auth.filter_by(email='%s' % id, passwd='%s' % passwd).first()
            logging.getLogger('sqlalchemy.engine').setLevel(savedLevel)
        except Exception as e:
            logging.getLogger('sqlalchemy.engine').setLevel(savedLevel)
            self.logger.error('Unexpected error while authenticating user: %s %s' % (id, e))
            res = None

        return res

def main(options, args):

    logname = 'promsdb'
    logger = log.get_logger(logname, options=options)

    try:
        s = ProMSdb(logger, options.dblog)
    except ProMSdbError as e:
        result = str(e)
        success = False
        logger.info('result %s success %s' % (result, success))
        exit(1)

    if options.id:
        res = s.user_in_proms(options.id)
        logger.info('user_in_proms result is %s' % res)
    if options.id and options.passwd:
        res = s.user_auth_in_proms(options.id, options.passwd)
        logger.info('user_auth_in_proms result is %s' % res)

if __name__ == "__main__":

    usage = "usage: %prog [options] [file] ..."
    from optparse import OptionParser
    optprs = OptionParser(usage=usage, version=('%prog'))

    optprs.add_option("--debug", dest="debug", default=False,
                      action="store_true",
                      help="Enter the pdb debugger on main()")

    optprs.add_option("-i", "--id", dest="id",
                      default=False,
                      help="User ID (e-mail)")

    optprs.add_option("-p", "--passwd", dest="passwd",
                      default=False,
                      help="User Password")

    optprs.add_option("--dblog", dest="dblog", action="store_true",
                      default=False,
                      help="Log DB commands")

    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    log.addlogopts(optprs)

    (options, args) = optprs.parse_args(sys.argv[1:])

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print "%s profile:" % sys.argv[0]
        profile.run('main(options, args)')

    else:
        main(options, args)
