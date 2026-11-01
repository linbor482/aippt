"""访问口令（HTTP Basic Auth）的行为测试。"""
import base64
import os
import tempfile
import unittest
from unittest.mock import patch

import auth as lan_auth
from app import app


def _basic(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode()).decode('ascii')
    return {'Authorization': f'Basic {token}'}


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_no_password_means_no_auth(self):
        with patch.dict(os.environ, {'ACCESS_PASSWORD': ''}):
            self.assertEqual(self.client.get('/api/config').status_code, 200)

    def test_missing_credentials_returns_401(self):
        with patch.dict(os.environ, {'ACCESS_PASSWORD': 'secret'}):
            response = self.client.get('/api/config')
            self.assertEqual(response.status_code, 401)
            self.assertIn('WWW-Authenticate', response.headers)

    def test_wrong_credentials_returns_401(self):
        with patch.dict(os.environ, {'ACCESS_PASSWORD': 'secret', 'ACCESS_USERNAME': 'admin'}):
            response = self.client.get('/api/config', headers=_basic('admin', 'wrong'))
            self.assertEqual(response.status_code, 401)

    def test_correct_credentials_returns_200(self):
        with patch.dict(os.environ, {'ACCESS_PASSWORD': 'secret', 'ACCESS_USERNAME': 'admin'}):
            response = self.client.get('/api/config', headers=_basic('admin', 'secret'))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()['success'])

    def test_custom_username_is_honoured(self):
        with patch.dict(os.environ, {'ACCESS_PASSWORD': 'secret', 'ACCESS_USERNAME': 'boss'}):
            self.assertEqual(self.client.get('/api/config', headers=_basic('admin', 'secret')).status_code, 401)
            self.assertEqual(self.client.get('/api/config', headers=_basic('boss', 'secret')).status_code, 200)


class LanAuthTests(unittest.TestCase):
    """auth.json 首次设置账密 + 局域网鉴权判定。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._path = patch('auth.AUTH_PATH', os.path.join(self._tmp.name, 'auth.json'))
        self._path.start()
        self.addCleanup(self._path.stop)
        self.addCleanup(self._tmp.cleanup)
        self._env = patch.dict(os.environ, {'ACCESS_PASSWORD': ''})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.client = app.test_client()

    def test_state_transitions_and_verify(self):
        self.assertEqual(lan_auth.state(), 'unset')
        lan_auth.setup('admin', 'secret123')
        self.assertEqual(lan_auth.state(), 'set')
        self.assertTrue(lan_auth.verify('admin', 'secret123'))
        self.assertFalse(lan_auth.verify('admin', 'wrong'))
        self.assertFalse(lan_auth.verify('boss', 'secret123'))
        lan_auth.skip()
        self.assertEqual(lan_auth.state(), 'skipped')

    def test_setup_rejects_weak_credentials(self):
        with self.assertRaises(ValueError):
            lan_auth.setup('', 'secret123')
        with self.assertRaises(ValueError):
            lan_auth.setup('admin', '123')

    def test_lan_mode_requires_auth_after_setup(self):
        with patch.dict(os.environ, {'HOST': '0.0.0.0'}):
            lan_auth.setup('admin', 'secret123')
            self.assertEqual(self.client.get('/api/config').status_code, 401)
            token = base64.b64encode(b'admin:secret123').decode('ascii')
            self.assertEqual(self.client.get('/api/config', headers={'Authorization': f'Basic {token}'}).status_code, 200)

    def test_local_host_never_requires_auth(self):
        with patch.dict(os.environ, {'HOST': '127.0.0.1'}):
            lan_auth.setup('admin', 'secret123')
            self.assertEqual(self.client.get('/api/config').status_code, 200)

    def test_auth_status_setup_skip_endpoints(self):
        self.assertEqual(self.client.get('/api/auth/status').get_json()['setup'], 'unset')
        self.assertEqual(self.client.post('/api/auth/setup', json={'username': 'admin', 'password': 'secret123'}).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/status').get_json()['setup'], 'set')
        self.assertEqual(self.client.post('/api/auth/setup', json={'username': '', 'password': 'secret123'}).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/skip').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/status').get_json()['setup'], 'skipped')


if __name__ == '__main__':
    unittest.main()
