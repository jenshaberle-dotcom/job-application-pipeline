"""Offline development suite for RCC; exercises real factory and receipt code.

No database, credentials, network, scheduler or runner registration is required.
Existing pure policy tests are included rather than copied into RCC.
"""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from src.connectors.classic_factory_delivery import DeliveryJournal, ReconciliationRequired, delivery_summary


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'receipt.json'
        self.binding = {'source_sha': 'test', 'population': 'bounded-fixture'}

    def test_success_survives_restart_without_repeating_effect(self):
        calls = []
        journal = DeliveryJournal(self.path, self.binding)
        def effect():
            self.assertEqual(DeliveryJournal(self.path, self.binding).data['stages']['build']['state'], 'RUNNING')
            calls.append(1)
            return {'built': 1}
        journal.stage('build', effect, effect=True)
        restored = DeliveryJournal(self.path, self.binding)
        self.assertEqual(restored.stage('build', effect, effect=True), {'built': 1})
        self.assertEqual(calls, [1])

    def test_uncertain_effect_stays_held_without_replay(self):
        journal = DeliveryJournal(self.path, self.binding)
        def fail():
            raise TimeoutError('private-detail')
        with self.assertRaises(TimeoutError):
            journal.stage('build', fail, effect=True)
        restored = DeliveryJournal(self.path, self.binding)
        with self.assertRaises(ReconciliationRequired):
            restored.stage('build', lambda: self.fail('replayed'), effect=True)
        self.assertNotIn('private-detail', ''.join(p.read_text() for p in journal.stage_dir.glob('*.json')))

    def test_changed_binding_is_rejected(self):
        DeliveryJournal(self.path, self.binding).save()
        with self.assertRaises(ValueError):
            DeliveryJournal(self.path, {'source_sha': 'different'})

    def test_read_only_failure_can_be_retried(self):
        journal = DeliveryJournal(self.path, self.binding)
        journal.data['stages']['check'] = {'state': 'RUNNING', 'effect': False}
        journal.save()
        self.assertEqual(DeliveryJournal(self.path, self.binding).stage('check', lambda: {'ok': True}, effect=False), {'ok': True})

    def test_bronze_is_not_end_to_end_acceptance(self):
        value = delivery_summary({'ingest:a': {'state': 'SUCCEEDED', 'result': {'observed_jobs': 2, 'inserted_jobs': 1}}}, 3)
        self.assertTrue(value['bronze_delivery_proven'])
        self.assertFalse(value['e2e_accepted'])
        self.assertFalse(value['profile_relevance_proven'])


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryTests)
    root = Path(__file__).resolve().parents[1]
    for name in ('test_aggressive_connector_factory', 'test_connector_factory_aggressive_policy'):
        spec = importlib.util.spec_from_file_location(name, root / 'tests' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for key, value in sorted(vars(module).items()):
            if key.startswith('test_') and callable(value):
                suite.addTest(unittest.FunctionTestCase(value))
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    return {'suite': 'jap-classic-connector-factory', 'tests_run': result.testsRun,
            'failures': len(result.failures), 'errors': len(result.errors),
            'skipped': len(result.skipped), 'successful': result.wasSuccessful(),
            'details': output.getvalue()[:8000]}


if __name__ == '__main__':
    result = run_suite()
    print(json.dumps(result))
    raise SystemExit(0 if result['successful'] else 1)
