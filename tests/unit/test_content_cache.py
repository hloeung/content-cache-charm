import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.modules['charms.apt'] = mock.MagicMock()
from charms import apt  # NOQA: E402

# Add path to where our reactive layer lives and import.
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
from reactive.content_cache import (
    upgrade_charm,
    install,
    config_changed,
    set_active,
    service_start_or_restart,
    configure_content_cache,
)  # NOQA: E402
from lib import nginx  # NOQA: E402,F401


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='charm-unittests-')
        self.charm_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

        patcher = mock.patch('charmhelpers.core.hookenv.log')
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_log.return_value = ''

        patcher = mock.patch('charmhelpers.core.hookenv.charm_dir')
        self.mock_charm_dir = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_charm_dir.return_value = self.charm_dir

        patcher = mock.patch('charmhelpers.core.hookenv.local_unit')
        self.mock_local_unit = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_local_unit.return_value = 'mock-content-cache/0'

        patcher = mock.patch('charmhelpers.core.hookenv.config')
        self.mock_config = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_config.return_value = {}

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @mock.patch('charmhelpers.core.hookenv.status_set')
    def test_hook_install_packages(self, status_set):
        install()
        expected = mock.call.queue_install(['haproxy', 'nginx'])
        self.assertTrue(expected in apt.method_calls)
        apt.install_queued.return_value = False
        install()
        expected = [mock.call('blocked', 'Unable to install packages')]
        self.assertEqual(status_set.call_args_list, expected)

    @mock.patch('charms.reactive.clear_flag')
    def test_hook_upgrade_charm_flags(self, clear_flag):
        upgrade_charm()
        expected = [mock.call('content_cache.active'),
                    mock.call('content_cache.installed'),
                    mock.call('content_cache.configured')]
        self.assertEqual(clear_flag.call_args_list, expected)

    @mock.patch('charms.reactive.clear_flag')
    @mock.patch('charms.reactive.set_flag')
    def test_hook_install_flags(self, set_flag, clear_flag):
        install()
        expected = [mock.call('content_cache.installed')]
        self.assertEqual(set_flag.call_args_list, expected)
        expected = [mock.call('content_cache.active'),
                    mock.call('content_cache.configured')]
        self.assertEqual(clear_flag.call_args_list, expected)

    @mock.patch('charms.reactive.clear_flag')
    def test_hook_config_changed_flags(self, clear_flag):
        config_changed()
        expected = [mock.call('content_cache.configured')]
        self.assertEqual(clear_flag.call_args_list, expected)

    @mock.patch('charms.reactive.set_flag')
    @mock.patch('charmhelpers.core.hookenv.status_set')
    def test_hook_set_active(self, status_set, set_flag):
        set_active()
        self.assertEqual(set_flag.call_args_list, [mock.call('content_cache.active')])
        self.assertEqual(status_set.call_args_list, [mock.call('active', 'ready')])

    @mock.patch('charmhelpers.core.host.service_running')
    @mock.patch('charmhelpers.core.host.service_restart')
    @mock.patch('charmhelpers.core.host.service_start')
    def test_service_start_or_restart_running(self, service_start, service_restart, service_running):
        service_running.return_value = True
        service_start_or_restart('someservice')
        self.assertEqual(service_start.call_args_list, [])
        self.assertEqual(service_restart.call_args_list, [mock.call('someservice')])

    @mock.patch('charmhelpers.core.host.service_running')
    @mock.patch('charmhelpers.core.host.service_restart')
    @mock.patch('charmhelpers.core.host.service_start')
    def test_service_start_or_restart_stopped(self, service_start, service_restart, service_running):
        service_running.return_value = False
        service_start_or_restart('someservice')
        self.assertEqual(service_start.call_args_list, [mock.call('someservice')])
        self.assertEqual(service_restart.call_args_list, [])

    @mock.patch('charms.reactive.clear_flag')
    @mock.patch('charmhelpers.core.hookenv.status_set')
    def test_configure_content_cache_no_sites(self, status_set, clear_flag):
        configure_content_cache()
        self.assertEqual(clear_flag.call_args_list, [mock.call('content_cache.active')])
        self.assertEqual(status_set.call_args_list, [mock.call('blocked', 'requires list of sites to configure')])

    @mock.patch('reactive.content_cache.service_start_or_restart')
    def test_configure_content_cache_sites(self, service_start_or_restart):
        with open('tests/unit/files/nginx_config_parse_test_config.txt', 'rb') as f:
            ngx_config = f.read().decode('utf-8')
        self.mock_config.return_value = {'sites': ngx_config}
        with mock.patch('lib.nginx.NginxConf.sites_path', new_callable=mock.PropertyMock) as mock_site_path:
            mock_site_path.return_value = self.tmpdir
            configure_content_cache()
            self.assertEqual(service_start_or_restart.call_args_list, [mock.call('nginx')])

        # Re-run with same set of sites.
        with mock.patch('lib.nginx.NginxConf.sites_path', new_callable=mock.PropertyMock) as mock_site_path:
            mock_site_path.return_value = self.tmpdir
            configure_content_cache()
            self.assertEqual(service_start_or_restart.call_args_list, [mock.call('nginx')])


if __name__ == '__main__':
    unittest.main()
