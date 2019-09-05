#
# Eric Jeschke (eric@naoj.org)
#

from datetime import datetime

# third-party imports
from pymongo import MongoClient

from qplan import entity
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

    def get_db_native_table(self, tbl_name):
        key = tbl_name.lower().replace(' ', '_')
        return self._qdb.mdb_db[key]

    def get_table(self, tbl_name):
        return QueueTable(self, tbl_name)

    def get_root_record(self, name):
        raise NotImplementedError("this method has been deprecated")

    def sync(self):
        # nop for mongodb
        pass

    def close(self):
        pass


class QueueTable(object):
    """
    qt = QueueTable(qa, 'executed_ob')
    """

    def __init__(self, qa, tbl_name):
        self._qa = qa
        self._tblname = tbl_name
        self.tbl = qa.get_db_native_table(tbl_name)
        self.logger = qa._qdb.logger
        self.make_fn = mdb2py_tbl_map[tbl_name]

    def get(self, **kwargs):
        try:
            rec = self.tbl.find_one(kwargs)
        except Exception as e:
            raise KeyError(str(kwargs))

        if self.make_fn is None:
            raise ValueError("Table '{}': no deserialization function to Python object".format(self._tblname))
        pyobj = self.make_fn(rec)
        return pyobj

    def put(self, pyobj):
        # sanity check that we are trying to save object to compatible table!
        if pyobj._tblname != self._tblname:
            raise ValueError("Trying to save '{}' object to '{}' table".format(pyobj._tblname, self._tblname))

        doc = pyobj.to_rec()
        # record time of last update for this entity
        doc['_save_tstamp'] = datetime.utcnow()
        self.tbl.update_one(pyobj.key, {'$set': doc}, upsert=True)


# Table map of serialization functions from MongoDB record to Python object.
# Used by QueueTable objects.
#
mdb2py_tbl_map = {
    'exposure': entity.make_exposure,
    'executed_ob': entity.make_executed_ob,
    'program': entity.make_program,
    }

#END
