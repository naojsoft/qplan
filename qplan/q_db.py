#
# E. Jeschke
#

from datetime import datetime
from dateutil import tz

# third-party imports
import yaml
from pymongo import MongoClient, UpdateOne

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
                 auth_mech='SCRAM-SHA-256', auth_src='auth_db', **kwargs):
        self.logger = logger
        if addr is None:
            addr = ('localhost', 9800)
        self.db_host, self.db_port = addr
        self.db_user = username
        self.db_pswd = password
        self.db_auth = auth_mech
        self.db_auth_src = auth_src
        self.db_conn_options = kwargs

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
        self.db_conn_options = cf.get('db_conn_options', {})

    def close(self):
        self.mdb_client.close()
        self.mdb_db = None

    def connect(self):
        kwargs = {}
        if self.db_user is not None:
            kwargs = dict(username=self.db_user, password=self.db_pswd,
                          authSource=self.db_auth_src,
                          authMechanism=self.db_auth)
            kwargs.update(self.db_conn_options)
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


# Number of operations to send in a single bulk_write.
default_chunk_size = 1000


def key_filter(key):
    """Turn an entity's `key` into a filter MongoDB can serve from an index.

    An array-valued field is expanded into positional predicates:
    {'ob_key': (proposal, name)} becomes
    {'ob_key.0': proposal, 'ob_key.1': name}.

    Matching the array as a whole works, but the index on such a field
    is multikey -- it indexes the elements separately -- so the first
    element alone matches every document sharing it, and the server
    fetches and filters that set. Against a real executed_ob collection,
    upserting new documents ran at 249/s matching the whole array and
    3413/s on the positional paths, and the gap widens as the collection
    grows.

    On an upsert that inserts, the document is built from $set, which
    carries the field in its proper array form, so the stored document
    is identical either way.

    Note this matches any array *beginning* with those elements. Every
    array-valued key in this module is fixed-length (an ob_key is always
    (proposal, name)), so the two are equivalent here.
    """
    filt = {}
    for field, value in key.items():
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                filt['{}.{}'.format(field, i)] = item
        else:
            filt[field] = value
    return filt


def update_op(pyobj, tstamp=None):
    """Return the (filter, update, upsert) for storing `pyobj`.

    An entity that came out of the database carries its _id, and that is
    what we target: it is the primary key, so the update is a single
    index hit.

    The alternative, and what this used to do unconditionally, is the
    entity's own `key`. For an Executed_OB that key matches the whole
    "ob_key" array, and the index on "ob_key" is multikey -- it indexes
    the array elements separately -- so the proposal id alone matches
    every executed_ob of the program and the server fetches and filters
    that whole set on every write. Measured against a real collection
    that is about 24 documents per second, against about 4400 by _id.
    PFS_Executed_OB_Stats has the same key shape and the same problem.

    An entity with no _id has not been stored yet, so it keeps the
    upsert on its key. Callers should copy the resulting _id back onto
    the object so later writes take the fast path.

    Note entity.explode() drops underscore-prefixed attributes, so _id
    is never in the document and $set cannot try to modify it.
    """
    if tstamp is None:
        tstamp = datetime.now(tz=tz.UTC)
    doc = pyobj.to_rec()
    # record time of last update for this entity
    doc['_save_tstamp'] = tstamp

    if pyobj._id is None:
        return key_filter(pyobj.key), {'$set': doc}, True
    return {'_id': pyobj._id}, {'$set': doc}, False


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

    def _check_table(self, pyobj):
        # sanity check that we are trying to save object to compatible table!
        if pyobj._tblname != self._tblname:
            raise ValueError("Trying to save '{}' object to '{}' table".format(pyobj._tblname, self._tblname))

    def put(self, pyobj):
        self._check_table(pyobj)

        filt, update, upsert = update_op(pyobj)
        result = self.tbl.update_one(filt, update, upsert=upsert)

        if upsert:
            # Remember where it landed, so a later write to the same
            # object can target it by _id.
            if result.upserted_id is not None:
                pyobj._id = result.upserted_id
            return

        if result.matched_count == 0:
            # We targeted an _id that is no longer there: the document
            # was removed between the read that produced this entity and
            # this write. Fall back to storing it under its own key.
            self.logger.warning(
                "'{}' document with _id {} no longer exists; "
                "storing it under its key instead".format(
                    self._tblname, pyobj._id))
            pyobj._id = None
            self.put(pyobj)

    def put_many(self, pyobjs, chunk_size=default_chunk_size):
        """Store many entities, batching them into bulk_write calls.

        put() issues one round trip per entity. For anything writing
        thousands of documents this is the method to use.

        Returns the number of documents written.
        """
        pyobjs = list(pyobjs)
        for pyobj in pyobjs:
            self._check_table(pyobj)

        n_written = 0
        for i in range(0, len(pyobjs), chunk_size):
            n_written += self._put_chunk(pyobjs[i:i + chunk_size])
        return n_written

    def _put_chunk(self, chunk):
        tstamp = datetime.now(tz=tz.UTC)
        ops, upserting, targeting = [], [], []
        for pyobj in chunk:
            filt, update, upsert = update_op(pyobj, tstamp)
            (upserting if upsert else targeting).append((len(ops), pyobj))
            ops.append(UpdateOne(filt, update, upsert=upsert))

        result = self.tbl.bulk_write(ops, ordered=False)

        # Remember where the new documents landed. bulk_write reports
        # these keyed by the index of the operation that created them.
        by_index = dict(upserting)
        for idx, oid in (result.upserted_ids or {}).items():
            pyobj = by_index.get(int(idx))
            if pyobj is not None:
                pyobj._id = oid

        if targeting and result.matched_count < len(targeting):
            self._recover_missing([pyobj for _, pyobj in targeting])

        return len(ops)

    def _recover_missing(self, pyobjs):
        """Re-store entities whose _id has disappeared from the database.

        bulk_write only reports how many operations matched, not which,
        so ask which of these _ids still exist and re-store the rest
        under their own keys.
        """
        ids = [pyobj._id for pyobj in pyobjs]
        alive = {rec['_id']
                 for rec in self.tbl.find({'_id': {'$in': ids}}, {'_id': 1})}
        missing = [pyobj for pyobj in pyobjs if pyobj._id not in alive]
        if not missing:
            return
        self.logger.warning(
            "{} '{}' documents no longer exist; storing them under their "
            "keys instead".format(len(missing), self._tblname))
        for pyobj in missing:
            pyobj._id = None
        self._put_chunk(missing)


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
