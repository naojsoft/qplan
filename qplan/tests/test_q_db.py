import logging
import unittest
from datetime import datetime
from dateutil import tz

from qplan import entity, q_db


class FakeCollection:
    """Enough of a pymongo Collection to exercise QueueTable's writes.

    Documents are held in a list. `_id`s are handed out as simple ints so
    assertions stay readable.
    """

    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.update_calls = []
        self.bulk_calls = []
        self.find_calls = []
        self._next_id = 100

    # -- helpers -----------------------------------------------------

    def _matches(self, doc, filt):
        for field, want in filt.items():
            if field == '_id':
                if doc.get('_id') != want:
                    return False
            elif doc.get(field) != want:
                return False
        return True

    def _apply(self, filt, update, upsert):
        """Return (matched, upserted_id)."""
        for doc in self.docs:
            if self._matches(doc, filt):
                doc.update(update['$set'])
                return 1, None
        if not upsert:
            return 0, None
        oid = self._next_id
        self._next_id += 1
        doc = dict(update['$set'])
        doc.update({k: v for k, v in filt.items() if k != '_id'})
        doc['_id'] = oid
        self.docs.append(doc)
        return 0, oid

    # -- the bits QueueTable uses ------------------------------------

    def update_one(self, filt, update, upsert=False):
        self.update_calls.append((filt, update, upsert))
        matched, oid = self._apply(filt, update, upsert)
        return type('R', (), {'matched_count': matched,
                              'modified_count': matched,
                              'upserted_id': oid})()

    def bulk_write(self, ops, ordered=True):
        self.bulk_calls.append(ops)
        matched = 0
        upserted_ids = {}
        for i, op in enumerate(ops):
            m, oid = self._apply(op._filter, op._doc, op._upsert)
            matched += m
            if oid is not None:
                upserted_ids[i] = oid
        return type('R', (), {'matched_count': matched,
                              'modified_count': matched,
                              'upserted_count': len(upserted_ids),
                              'upserted_ids': upserted_ids})()

    def find(self, filt, projection=None):
        self.find_calls.append(filt)
        ids = filt['_id']['$in']
        return [{'_id': d['_id']} for d in self.docs if d.get('_id') in ids]


class FakeAdapter:
    def __init__(self, collection):
        self.collection = collection
        self.logger = logging.getLogger('test_q_db')
        self._qdb = type('D', (), {'logger': self.logger})()

    def get_db_native_table(self, tbl_name):
        return self.collection


def make_table(docs=None):
    coll = FakeCollection(docs)
    return q_db.QueueTable(FakeAdapter(coll), 'executed_ob'), coll


def an_executed_ob(name='OB1'):
    ex = entity.Executed_OB(('S25A-000QF', name), insname='PFS')
    ex.time_start = datetime(2025, 11, 29, 3, 0, 0, tzinfo=tz.UTC)
    ex.time_stop = ex.time_start
    return ex


class TestEntityId(unittest.TestCase):

    def test_new_entity_has_no_id(self):
        self.assertIsNone(an_executed_ob()._id)

    def test_id_is_not_stored_in_the_document(self):
        """explode() drops underscore attributes, so an update can never
        try to modify the immutable _id."""
        ex = an_executed_ob()
        ex._id = 42
        doc = ex.to_rec()
        self.assertNotIn('_id', doc)
        self.assertNotIn('_tblname', doc)

    def test_from_rec_picks_up_the_id(self):
        ex = entity.Executed_OB()
        ex.from_rec({'_id': 7, 'ob_key': ['S25A-000QF', 'OB1'],
                     'time_start': None, 'time_stop': None,
                     'exp_history': [], 'insname': 'PFS'})
        self.assertEqual(ex._id, 7)


class TestUpdateOp(unittest.TestCase):

    def test_new_entity_upserts_on_its_key(self):
        ex = an_executed_ob()
        filt, update, upsert = q_db.update_op(ex)
        self.assertEqual(filt, ex.key)
        self.assertTrue(upsert)
        self.assertIn('_save_tstamp', update['$set'])

    def test_stored_entity_targets_its_id(self):
        """The whole point: not the multikey ob_key array."""
        ex = an_executed_ob()
        ex._id = 42
        filt, update, upsert = q_db.update_op(ex)
        self.assertEqual(filt, {'_id': 42})
        self.assertFalse(upsert)


class TestPut(unittest.TestCase):

    def test_put_new_entity_upserts_and_records_the_id(self):
        qt, coll = make_table()
        ex = an_executed_ob()
        qt.put(ex)

        filt, update, upsert = coll.update_calls[0]
        self.assertEqual(filt, ex.key)
        self.assertTrue(upsert)
        # the object now knows where it lives, so a second write is cheap
        self.assertIsNotNone(ex._id)

    def test_second_put_targets_the_id(self):
        qt, coll = make_table()
        ex = an_executed_ob()
        qt.put(ex)
        qt.put(ex)

        self.assertEqual(coll.update_calls[1][0], {'_id': ex._id})
        self.assertFalse(coll.update_calls[1][2])
        self.assertEqual(len(coll.docs), 1)

    def test_put_stored_entity_updates_in_place(self):
        qt, coll = make_table([{'_id': 5, 'ob_key': ['S25A-000QF', 'OB1'],
                                'iqa': ''}])
        ex = an_executed_ob()
        ex._id = 5
        ex.iqa = 'good'
        qt.put(ex)

        self.assertEqual(coll.update_calls[0][0], {'_id': 5})
        self.assertEqual(coll.docs[0]['iqa'], 'good')
        self.assertEqual(len(coll.docs), 1)

    def test_put_recovers_when_the_document_was_deleted(self):
        """Targeting an _id that has gone must not silently do nothing."""
        qt, coll = make_table()
        ex = an_executed_ob()
        ex._id = 999          # never existed

        qt.put(ex)

        # first attempt by _id, then a fallback upsert on the key
        self.assertEqual(coll.update_calls[0][0], {'_id': 999})
        self.assertEqual(coll.update_calls[1][0], ex.key)
        self.assertTrue(coll.update_calls[1][2])
        self.assertEqual(len(coll.docs), 1)

    def test_put_rejects_the_wrong_table(self):
        qt, _ = make_table()
        with self.assertRaises(ValueError):
            qt.put(entity.PFS_Exposure())


class TestPutMany(unittest.TestCase):

    def test_writes_every_entity(self):
        qt, coll = make_table()
        obs = [an_executed_ob(f'OB{i}') for i in range(5)]
        self.assertEqual(qt.put_many(obs), 5)
        self.assertEqual(len(coll.docs), 5)

    def test_batches_into_chunks(self):
        qt, coll = make_table()
        obs = [an_executed_ob(f'OB{i}') for i in range(7)]
        qt.put_many(obs, chunk_size=3)
        self.assertEqual([len(c) for c in coll.bulk_calls], [3, 3, 1])

    def test_records_ids_of_new_documents(self):
        """So a later write to the same objects takes the fast path."""
        qt, coll = make_table()
        obs = [an_executed_ob(f'OB{i}') for i in range(3)]
        qt.put_many(obs)
        self.assertTrue(all(ob._id is not None for ob in obs))
        self.assertEqual(len({ob._id for ob in obs}), 3)

        coll.bulk_calls.clear()
        qt.put_many(obs)
        for op in coll.bulk_calls[0]:
            self.assertIn('_id', op._filter)
            self.assertFalse(op._upsert)
        self.assertEqual(len(coll.docs), 3)

    def test_recovers_only_the_documents_that_vanished(self):
        qt, coll = make_table()
        obs = [an_executed_ob(f'OB{i}') for i in range(3)]
        qt.put_many(obs)

        # one of them disappears from under us
        gone = obs[1]
        coll.docs = [d for d in coll.docs if d['_id'] != gone._id]
        coll.bulk_calls.clear()

        qt.put_many(obs)

        # asked which ids still exist, then re-stored just the one
        self.assertEqual(len(coll.find_calls), 1)
        recovery = coll.bulk_calls[-1]
        self.assertEqual(len(recovery), 1)
        self.assertTrue(recovery[0]._upsert)
        self.assertEqual(len(coll.docs), 3)

    def test_rejects_the_wrong_table_before_writing_anything(self):
        qt, coll = make_table()
        with self.assertRaises(ValueError):
            qt.put_many([an_executed_ob(), entity.PFS_Exposure()])
        self.assertEqual(coll.bulk_calls, [])


if __name__ == '__main__':
    unittest.main()
