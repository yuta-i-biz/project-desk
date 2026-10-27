"""Connection ownership: persistence, rollback, and deterministic release."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import Desk
from workspace import register


class ConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.desk = Desk(self.root / 'home', self.root / 'data')

    def assertClosed(self, connection):
        try:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')
        finally:
            connection.close()

    def test_commit_and_close(self):
        with self.desk.connect() as connection:
            self.assertEqual(connection.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            connection.execute('CREATE TABLE lifecycle(value TEXT)')
            connection.execute("INSERT INTO lifecycle VALUES('saved')")
        try:
            with self.desk.connect() as check:
                self.assertEqual(check.execute('SELECT value FROM lifecycle').fetchone()[0], 'saved')
        finally:
            self.assertClosed(connection)

    def test_rollback_and_close(self):
        with self.desk.connect() as setup:
            setup.execute('CREATE TABLE lifecycle(value TEXT)')
        with self.assertRaisesRegex(ValueError, 'abort'):
            with self.desk.connect() as connection:
                connection.execute("INSERT INTO lifecycle VALUES('discard')")
                raise ValueError('abort')
        try:
            with self.desk.connect() as check:
                self.assertEqual(check.execute('SELECT count(*) FROM lifecycle').fetchone()[0], 0)
        finally:
            self.assertClosed(connection)

    def test_registration_success_closes_connection(self):
        self.check_registration(True)

    def test_registration_failure_closes_connection(self):
        self.check_registration(False)

    def check_registration(self, valid):
        pid = self.desk.mutate('project', {'name': 'Fixture', 'company': 'Test'})['id']
        connection = sqlite3.connect(self.desk.db)
        with patch('workspace.validate', return_value=self.root / 'source'), patch('workspace.sqlite3.connect', return_value=connection):
            if valid:
                self.assertTrue(register(self.desk.data, pid, self.root / 'source', self.root)['registered'])
            else:
                with self.assertRaises(ValueError):
                    register(self.desk.data, 'missing', self.root / 'source', self.root)
        self.assertClosed(connection)
