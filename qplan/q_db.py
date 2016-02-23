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

        self.conn = self.db.open()
        self.dbroot = self.conn.root()

        # Check whether database is initialized
        for name in ['program', 'ob', 'executed_ob', 'exposure']:
            key = '%s_db' % name
            if not self.dbroot.has_key(key):
                self.dbroot[key] = OOBTree()

                transaction.commit()

    def close(self):
        self.conn.close()
        self.db.close()
        self.storage.close()

    def get_adaptor(self):
        return QueueAdaptor(self)


class QueueAdaptor(object):
    """
    Each thread should use its own QueueAdaptor.

    qa = QueueAdaptor(db)
    """

    def __init__(self, qdb):
        self._qdb = qdb
        self.logger = qdb.logger

        self.conn = self._qdb.db.open()
        self.dbroot = self.conn.root()

    def get_table(self, name):
        key = '%s_db' % name
        return self.dbroot[key]

    def close(self):
        self.conn.close()


#END
