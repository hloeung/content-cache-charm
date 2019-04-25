import os
import shutil
import sys
import tempfile
import unittest
import yaml

import freezegun

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
from lib import haproxy as HAProxy  # NOQA: E402


class TestLibHAProxy(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.tmpdir = tempfile.mkdtemp(prefix='charm-unittests-')
        self.addCleanup(shutil.rmtree, self.tmpdir)
        self.charm_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
        with open('tests/unit/files/config_test_config.txt', 'r', encoding='utf-8') as f:
            self.site_config = yaml.safe_load(f.read())

    def test_haproxy_config_path(self):
        conf_path = '/etc/haproxy'
        haproxy = HAProxy.HAProxyConf()
        self.assertEqual(haproxy.conf_path, conf_path)

    def test_haproxy_config_file(self):
        conf_file = '/etc/haproxy/haproxy.cfg'
        haproxy = HAProxy.HAProxyConf()
        self.assertEqual(haproxy.conf_file, conf_file)

    def test_haproxy_config_generate_stanza_names(self):
        haproxy = HAProxy.HAProxyConf(self.tmpdir)
        self.assertEqual(haproxy._generate_stanza_name('site1'), 'site1')
        self.assertEqual(haproxy._generate_stanza_name('site1.local'), 'site1-local')
        self.assertEqual(haproxy._generate_stanza_name('site1-canonical-com-canonical-com'),
                         'site1-canonical-com-canonical-co')
        self.assertEqual(haproxy._generate_stanza_name('site1.local', ['site1-local']), 'site1-local-2')
        self.assertEqual(haproxy._generate_stanza_name('site1.local', ['site1-local', 'site1-local-2']),
                         'site1-local-3')

    def test_haproxy_config_rendered_listen_stanzas(self):
        haproxy = HAProxy.HAProxyConf(self.tmpdir)
        config = self.site_config
        with open('tests/unit/files/haproxy_config_rendered_listen_stanzas_test_output.txt', 'r',
                  encoding='utf-8') as f:
            want = f.read()
        self.assertEqual(''.join(haproxy.render_stanza_listen(config)), want)

        # Test overriding backend-names
        for site in config.keys():
            config[site]['backend-name'] = site
        self.assertEqual(''.join(haproxy.render_stanza_listen(config)), want)

    @freezegun.freeze_time("2019-03-22", tz_offset=0)
    def test_haproxy_config_rendered_backend_stanzas(self):
        haproxy = HAProxy.HAProxyConf(self.tmpdir)
        config = self.site_config
        with open('tests/unit/files/haproxy_config_rendered_backends_stanzas_test_output.txt', 'r',
                  encoding='utf-8') as f:
            want = f.read()
        self.assertEqual(''.join(haproxy.render_stanza_backend(config)), want)

    @freezegun.freeze_time("2019-03-22", tz_offset=0)
    def test_haproxy_config_rendered_full_config(self):
        haproxy = HAProxy.HAProxyConf(self.tmpdir)
        config = self.site_config
        num_procs = 4
        password = "biometricsarenotsecret"
        self.assertTrue(haproxy.write(haproxy.render(config, num_procs, monitoring_password=password)))
        with open(haproxy.conf_file, 'r') as f:
            new_conf = f.read()
        with open('tests/unit/files/haproxy_config_rendered_test_output.txt', 'r') as f:
            want = f.read()
        self.assertEqual(new_conf, want)

    def test_haproxy_config_write(self):
        haproxy = HAProxy.HAProxyConf(self.tmpdir)
        with open('tests/unit/files/haproxy_config_rendered_test_output.txt', 'r', encoding='utf-8') as f:
            conf = f.read()
        self.assertTrue(haproxy.write(conf))
        # Write again with same contents, this time it should return 'False'
        # as there should be no change.
        self.assertFalse(haproxy.write(conf))

    def test_haproxy_config_merge_listen_stanzas(self):
        haproxy = HAProxy.HAProxyConf(self.tmpdir)
        config = {
            'site1.local': {'port': 80},
            'site2.local': {'port': 80},
            'site3.local': {},
            'site4.local': {'port': 443},
            'site5.local': {'tls-cert-bundle-path': '/tmp/somepath'},
        }
        want = {
            '0.0.0.0:80': {
                'site1.local': {'port': 80},
                'site2.local': {'port': 80},
                'site3.local': {'port': 80},
            },
            '0.0.0.0:443': {
                'site4.local': {'port': 443},
                'site5.local': {'port': 443,
                                'tls-cert-bundle-path': '/tmp/somepath'},
            },
        }
        self.assertEqual(haproxy._merge_listen_stanzas(config), want)
