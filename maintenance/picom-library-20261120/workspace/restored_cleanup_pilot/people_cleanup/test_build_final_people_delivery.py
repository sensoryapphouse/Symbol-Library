import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build_final_people_delivery as builder


def receipt(path, code='a'):
    return {'path': str(path), 'expected_sha256': code*64, 'actual_sha256': code*64,
            'bytes': 123, 'matches': True, 'stable_during_read': True}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.library = Path('/example/Library')
        self.rows = []
        for i, status in enumerate(('accepted', 'accepted_prior_repair', 'below_eligibility_unprocessed')):
            relative = f'Style/Category/symbol {i}.webp'
            source = receipt(self.library/relative)
            delivery = receipt(Path('/example/delivery')/f'{i}.webp', 'b') if i < 2 else copy.deepcopy(source)
            self.rows.append({'invocation': 'verified-pass', 'relative_path': relative, 'source_id': str(i),
                              'status': status, 'passed': True, 'source': source, 'delivery': delivery})
        self.proof = {'invocation': 'verified-pass', 'scope_total': 3,
                      'status_counts': {r['status']: 1 for r in self.rows}}

    def validate(self, rows=None):
        return builder.validate_records(self.rows if rows is None else rows, self.proof, self.library)

    def test_cleanup_repair_and_unchanged_identity_are_preserved(self):
        catalog = self.validate()
        self.assertEqual([r['delivery_kind'] for r in catalog], ['cleaned', 'repair', 'original'])
        self.assertEqual(catalog[2]['delivery_path'], catalog[2]['source_path'])

    def test_incomplete_and_duplicate_scope_rejected(self):
        for rows in (self.rows[:-1], [self.rows[0], self.rows[0], self.rows[2]]):
            with self.assertRaises(ValueError):
                self.validate(rows)

    def test_bad_or_unstable_receipts_rejected(self):
        for field, value in (('matches', False), ('stable_during_read', False), ('actual_sha256', 'c'*64)):
            rows = copy.deepcopy(self.rows)
            rows[0]['delivery'][field] = value
            with self.assertRaises(ValueError):
                self.validate(rows)

    def test_wrong_invocation_original_or_output_rejected(self):
        changes = [(0, 'invocation', 'different'), (0, 'status', 'unreviewed')]
        for i, field, value in changes:
            rows = copy.deepcopy(self.rows)
            rows[i][field] = value
            with self.assertRaises(ValueError):
                self.validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]['delivery'] = copy.deepcopy(rows[0]['source'])
        with self.assertRaises(ValueError):
            self.validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[2]['delivery'] = receipt('/example/other.webp')
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_final_verification_gate_refuses_pending_or_tampered_proof(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(builder, 'VERIFICATION', Path(tmp)):
            pointer = Path(tmp)/'latest_status.json'
            pointer.write_text(json.dumps({'status': 'blocked', 'completion_claim': False}))
            with self.assertRaisesRegex(ValueError, 'has not completed'):
                builder.load_verified_catalog()
            proof = Path(tmp)/'proof.json'
            proof.write_text('{}')
            pointer.write_text(json.dumps({'status': 'complete', 'completion_claim': True,
                                           'proof_path': str(proof), 'proof_sha256': '0'*64}))
            with self.assertRaisesRegex(ValueError, 'Changed proof'):
                builder.load_verified_catalog()

    def test_html_embedded_data_cannot_close_script(self):
        catalog = self.validate()[:2]
        catalog[0]['relative_path'] = 'Style/</script><script>bad</script>.webp'
        page = builder.render_index(catalog, {'scope_total': 3})
        self.assertNotIn('</script><script>bad', page)
        self.assertIn('\\u003c/script>', page)
        self.assertIn('file:///example/', page)


if __name__ == '__main__':
    unittest.main()
