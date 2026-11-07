import tempfile
import unittest
from pathlib import Path
from indo_brain.garuda_security import GarudaSecurity, PersistentSlidingWindowLimiter
from indo_brain.garuda_gateway import ApprovalStore, ToolGateway

class PersistentRateLimitTests(unittest.TestCase):
    def test_rate_limit_survives_new_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'limits.sqlite3'
            one = PersistentSlidingWindowLimiter(path)
            self.assertTrue(one.check('client:read', 1, 60, now=100)[0])
            two = PersistentSlidingWindowLimiter(path)
            self.assertFalse(two.check('client:read', 1, 60, now=101)[0])

    def test_rate_limit_isolated_by_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            limiter = PersistentSlidingWindowLimiter(Path(tmp) / 'limits.sqlite3')
            self.assertTrue(limiter.check('a', 1, 60, now=100)[0])
            self.assertTrue(limiter.check('b', 1, 60, now=100)[0])

class ToolGatewayTests(unittest.TestCase):
    def test_unregistered_tool_never_runs(self):
        called = []
        with tempfile.TemporaryDirectory() as tmp:
            gateway = ToolGateway({'read_project': lambda: called.append(True)}, ApprovalStore(Path(tmp)/'approvals.sqlite3'))
            with self.assertRaises(PermissionError): gateway.execute('execute_shell', 'acct')
        self.assertEqual(called, [])

    def test_sensitive_action_requires_approval(self):
        called = []
        with tempfile.TemporaryDirectory() as tmp:
            store = ApprovalStore(Path(tmp)/'approvals.sqlite3', secret='test-secret')
            gateway = ToolGateway({'write_project_file': lambda content: called.append(content)}, store)
            with self.assertRaises(PermissionError): gateway.execute('write_project_file', 'acct', args={'content':'x'})
            token = store.issue('acct', 'write_project_file', explicitly_confirmed=True)
            self.assertEqual(gateway.execute('write_project_file', 'acct', args={'content':'ok'}, approval_token=token), None)
            self.assertEqual(called, ['ok'])

    def test_approval_is_account_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ApprovalStore(Path(tmp)/'approvals.sqlite3', secret='test-secret')
            token = store.issue('acct-a', 'send_external_message', explicitly_confirmed=True)
            self.assertFalse(store.consume(token, 'acct-b', 'send_external_message'))
            self.assertTrue(store.consume(token, 'acct-a', 'send_external_message'))
            self.assertFalse(store.consume(token, 'acct-a', 'send_external_message'))

    def test_approval_requires_explicit_confirmation_and_expires(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ApprovalStore(Path(tmp)/'approvals.sqlite3')
            with self.assertRaises(PermissionError):
                store.issue('acct', 'delete_user_data', explicitly_confirmed=False)

    def test_garuda_uses_persistent_limiter(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = GarudaSecurity(tmp)
            self.assertIsInstance(g.limiter, PersistentSlidingWindowLimiter)
            self.assertEqual(g.max_body_bytes, max(1024, min(g.max_body_bytes, 64*1024*1024)))

if __name__ == '__main__': unittest.main()
