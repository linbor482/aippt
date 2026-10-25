"""访问口令（HTTP Basic Auth）的行为测试。"""
import base64
import os
import unittest
from unittest.mock import patch

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


if __name__ == '__main__':
    unittest.main()
