import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('core', ROOT / 'addon/core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
spec2 = importlib.util.spec_from_file_location('build', ROOT / 'tools/build.py')
builder = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(builder)


class ConfigTest(unittest.TestCase):
    def config(self):
        return dict(binary=sys.executable, tunnel_id='tunnel_' + 'a' * 32,
                    organization_id='', mcp_url='http://127.0.0.1:3141/')

    def test_portable_binary_path(self):
        with tempfile.TemporaryDirectory(prefix='path with spaces ') as tmp:
            binary = Path(tmp) / 'tunnel-client.exe'
            binary.write_text('test')
            config = self.config(); config['binary'] = str(binary)
            self.assertEqual(core.validate(config)['binary'], str(binary.resolve()))

    def test_invalid_mcp_destinations(self):
        for url in ['http://example.com:3141/', 'http://127.0.0.1:3141@evil.test/',
                    'http://user:secret@127.0.0.1:3141/', 'http://127.0.0.1:3141/?secret=x',
                    'file:///tmp/server', 'http://127.0.0.1:99999/', 'http://127.0.0.1/']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                config = self.config(); config['mcp_url'] = url; core.validate(config)

    def test_ipv6_loopback(self):
        config = self.config(); config['mcp_url'] = 'http://[::1]:3141/'
        self.assertEqual(core.validate(config)['mcp_url'], config['mcp_url'])

    def test_namespaced_tunnel(self):
        config = self.config(); config['tunnel_id'] = 'tunnel_ab12_' + 'a' * 32
        core.validate(config)
        config['tunnel_id'] = 'tunnel_invalid'
        with self.assertRaises(ValueError): core.validate(config)

    def test_organization_header_validation(self):
        config = self.config(); config['organization_id'] = 'org-test\r\nAuthorization: bad'
        with self.assertRaises(ValueError): core.validate(config)

    def test_profile_has_no_secret(self):
        result = core.profile(core.validate(self.config()), Path('health.url'))
        self.assertEqual(result['control_plane']['api_key'], 'env:CONTROL_PLANE_API_KEY')
        self.assertEqual(result['health']['listen_addr'], '127.0.0.1:0')
        self.assertEqual(result['log']['file'], 'stdout')

    def test_redaction(self):
        self.assertEqual(core.redact('error abc-secret sk-example123', 'abc-secret'),
                         'error [REDACTED] [REDACTED]')

    def test_health_file_rejects_remote_and_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'health.url'
            for value in ['http://remote.test:8080', 'http://user:pass@127.0.0.1:8080',
                          'http://127.0.0.1:8080/remote', 'http://127.0.0.1:8080?q=x']:
                p.write_text(value)
                with self.subTest(value=value), self.assertRaises(ValueError): core.health_url(p)
            p.write_text('http://127.0.0.1:8080\n')
            self.assertEqual(core.health_url(p), 'http://127.0.0.1:8080')

    def test_package_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = builder.build(Path(tmp) / 'test.ankiaddon')
            with ZipFile(path) as archive:
                self.assertEqual(set(archive.namelist()), set(builder.FILES))
                config = json.loads(archive.read('config.json'))
                self.assertEqual(config['tunnel_id'], '')
                self.assertNotIn('api_key', config)


if __name__ == '__main__': unittest.main()
