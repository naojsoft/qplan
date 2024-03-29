#!/usr/bin/env python

# Connect to the ProMS MySQL user database. Includes queries for ProMS
# ID and ProMS ID/password.

import os, sys
import mysql.connector
import sqlalchemy
import logging
from sqlsoup import SQLSoup as SqlSoup
import bcrypt

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

        engine = sqlalchemy.create_engine('mysql+mysqlconnector://', creator=self.getconn_mysqldb)
        self.db = SqlSoup(engine)
        try:
            self.auth = self.db.auth # "auth" table
        except Exception as e:
            msg = 'Unexpected error while connecting to PROMS_DB_SERVER: %s' % e[1]
            self.logger.error(msg)
            raise ProMSdbError(msg)

    def getconn_mysqldb(self):
        c = mysql.connector.connect(host=self.server, user=self.user, password=self.passwd, database=self.dbname)
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
            res = self.auth.filter_by(email='%s' % id).first()
            self.logger.info('res is %s' % str(res))
            if res:
                auth_check = bcrypt.checkpw(passwd.encode('UTF-8'), res.passwd.encode('UTF-8'))
            else:
                auth_check = False
            self.logger.info('auth_check is %s' % auth_check)
            logging.getLogger('sqlalchemy.engine').setLevel(savedLevel)
        except Exception as e:
            logging.getLogger('sqlalchemy.engine').setLevel(savedLevel)
            self.logger.error('Unexpected error while authenticating user: %s %s' % (id, e))
            res = None

        return res, auth_check

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
        sres, auth_check = s.user_auth_in_proms(options.id, options.passwd)
        logger.info('user_auth_in_proms result is %s, auth_check is %s' % (sres, auth_check))

if __name__ == "__main__":

    from argparse import ArgumentParser
    argprs = ArgumentParser(description="Query PROMS DB")

    argprs.add_option("-i", "--id", dest="id",
                      default=False,
                      help="User ID (e-mail)")

    argprs.add_option("-p", "--passwd", dest="passwd",
                      default=False,
                      help="User Password")

    argprs.add_option("--dblog", dest="dblog", action="store_true",
                      default=False,
                      help="Log DB commands")

    log.addlogopts(argprs)

    (options, args) = argprs.parse_known_args(sys.argv[1:])

    main(options, args)
