#
# Eric Jeschke (eric@naoj.org)
#

from datetime import datetime

# third-party imports
from pymongo import MongoClient

"""
    Server:
    $ mongod -a host:port -f /path/to/db/dir

"""

class QueueDatabase(object):
    """
    There should be one QueueDatabase instance per process.

    Usage example:
      addr = ('localhost', 9800)
      db = QueueDatabase(logger, addr)
    """

    def __init__(self, logger, addr):
        self.logger = logger
        self.db_host, self.db_port = addr

        self.mdb_client = None
        self.mdb_db = None

        self.reconnect()

    def close(self):
        self.mdb_client.close()
        self.mdb_db = None

    def reconnect(self):
        self.mdb_client = MongoClient(self.db_host, self.db_port)
        self.mdb_db = self.mdb_client['queue_db']

    def get_adaptor(self):
        return QueueAdapter(self)


class QueueAdapter(object):
    """
    Each thread should use its own QueueAdapter.

    qa = QueueAdapter(db)
    """

    def __init__(self, qdb):
        self._qdb = qdb
        self.logger = qdb.logger

    def get_table(self, name):
        key = name.lower().replace(' ', '_')
        return self._qdb.mdb_db[key]

    def get_root_record(self, name):
        return self.get_table(name)

    def store_table(self, name, pyobj):
        tbl = self.get_table(name)
        doc = pyobj.to_rec()
        # record time of last update for this entity
        doc['_save_tstamp'] = datetime.utcnow()
        tbl.update_one(pyobj.key, {'$set': doc}, upsert=True)

    def sync(self):
        # nop for mongodb
        pass

    def close(self):
        pass


#END
