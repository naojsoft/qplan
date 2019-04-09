#
# Eric Jeschke (eric@naoj.org)
#

# third-party imports
from ZODB import FileStorage, DB
from BTrees.OOBTree import OOBTree
from ZEO import ClientStorage
import transaction
from persistent import Persistent

"""
    Server:
    $ runzeo -a host:port -f /path/to/db/file

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
        #storage = FileStorage.FileStorage(dbfile)
        self.storage = ClientStorage.ClientStorage(addr)
        self.db = DB(self.storage)

        self.transaction_manager = transaction.TransactionManager()
        self.conn = self.db.open(self.transaction_manager)
        self.dbroot = self.conn.root()

        with self.transaction_manager:
            # Check whether database is initialized
            for name in ['program', 'ob', 'executed_ob', 'exposure',
                         'saved_state']:
                key = '%s_db' % name
                if key not in self.dbroot:
                    tbl = OOBTree()
                    self.dbroot[key] = tbl

            if 'queue_mgmt' not in self.dbroot:
                self.dbroot['queue_mgmt'] = QueueMgmtRec()

    def close(self):
        self.conn.close()
        self.db.close()
        self.storage.close()

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

        self.conn = self._qdb.conn
        self.dbroot = self._qdb.dbroot

    def get_table(self, name):
        key = '%s_db' % name
        return self.dbroot[key]

    def get_root_record(self, name):
        return self.dbroot[name]

    def sync(self):
        self._qdb.conn.sync()

    def close(self):
        self.conn.close()


class QueueMgmtRec(Persistent):

    def __init__(self):
        super(QueueMgmtRec, self).__init__()

        self.current_executed = None
        self.time_update = None


#END
