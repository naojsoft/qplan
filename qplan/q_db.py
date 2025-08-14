#
# E. Jeschke
#

from datetime import datetime
from dateutil import tz

# third-party imports
import yaml
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
      db = QueueDatabase(logger, addr=addr)
    """

    def __init__(self, logger, addr=None, username=None, password=None,
                 auth_mech='SCRAM-SHA-256', auth_src='auth_db'):
        self.logger = logger
        if addr is None:
            addr = ('localhost', 9800)
        self.db_host, self.db_port = addr
        self.db_user = username
        self.db_pswd = password
        self.db_auth = auth_mech
        self.db_auth_src = auth_src

        self.mdb_client = None
        self.mdb_db = None

    def read_config(self, cfg_path):
        with open(cfg_path, 'r') as in_f:
            buf = in_f.read()
        cf = yaml.safe_load(buf)

        self.db_host = cf.get('db_host', 'localhost')
        self.db_port = cf.get('db_port', 9800)
        self.db_user = cf.get('db_user', None)
        self.db_pswd = cf.get('db_pass', None)
        self.db_auth = cf.get('db_auth', 'SCRAM-SHA-256')
        self.db_auth_src = cf.get('auth_src', 'auth_db')

    def close(self):
        self.mdb_client.close()
        self.mdb_db = None

    def connect(self):
        kwargs = {}
        if self.db_user is not None:
            kwargs = dict(username=self.db_user, password=self.db_pswd,
                          authSource=self.db_auth_src,
                          authMechanism=self.db_auth)
        self.mdb_client = MongoClient(self.db_host, self.db_port,
                                      **kwargs)
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
        if rec is None:
            raise KeyError(str(kwargs))

        if self.make_fn is None:
            raise ValueError("Table '{}': no deserialization function to Python object".format(self._tblname))
        pyobj = self.make_fn(rec)
        if pyobj is None:
            raise ValueError("Use q_query functions to get '{}' objects".format(self._tblname))
        return pyobj

    def put(self, pyobj):
        # sanity check that we are trying to save object to compatible table!
        if pyobj._tblname != self._tblname:
            raise ValueError("Trying to save '{}' object to '{}' table".format(pyobj._tblname, self._tblname))

        doc = pyobj.to_rec()
        # record time of last update for this entity
        doc['_save_tstamp'] = datetime.now(tz=tz.UTC)
        self.tbl.update_one(pyobj.key, {'$set': doc}, upsert=True)


# Table map of serialization functions from MongoDB record to Python object.
# Used by QueueTable objects.
#
mdb2py_tbl_map = {
    'exposure': entity.make_exposure,
    'executed_ob': entity.make_executed_ob,
    'pfs_executed_ob_stats': entity.make_pfs_executed_ob_stats,
    'program': entity.make_program,
    'program_stats': entity.make_program_stats,
    'hsc_program_stats': entity.make_hsc_program_stats,
    'pfs_program_stats': entity.make_pfs_program_stats,
    'intensive_program': entity.make_intensive_program,
    'saved_state': entity.make_saved_state,
    'pfs_executed_ob_status': entity.make_pfs_executed_ob_status,
    'pfs_executed_ob_stats_status': entity.make_pfs_executed_ob_stats_status,
    'ob': lambda dct: None,
    }

#END
