import os
import shutil
import sys
import tempfile
import unittest
import yaml
from unittest import mock

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
from lib import nginx  # NOQA: E402


class TestLibNginx(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='charm-unittests-')
        self.charm_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_nginx_config_sites_path(self):
        sites_path = '/etc/nginx/sites-available'
        ngx_conf = nginx.NginxConf()
        self.assertEqual(ngx_conf.sites_path, sites_path)

    def test_nginx_config_parse(self):
        ngx_conf = nginx.NginxConf()
        with open('tests/unit/files/nginx_config_parse_test_config.txt', 'rb') as f:
            conf = yaml.safe_load(f.read().decode('utf-8'))
        for site in conf.keys():
            output_file = 'tests/unit/files/nginx_config_parse_test_output-{}.txt'.format(site)
            with open(output_file, 'rb') as f:
                output = f.read().decode('utf-8')
            self.assertEqual(output, ngx_conf.parse(conf[site]))

    def test_nginx_config_write(self):
        ngx_conf = nginx.NginxConf()
        conf_file = 'tests/unit/files/nginx_config_parse_test_output-site1.local.txt'
        with open(conf_file, 'rb') as f:
            conf = f.read().decode('utf-8')
        with mock.patch('lib.nginx.NginxConf.sites_path', new_callable=mock.PropertyMock) as mock_site_path:
            mock_site_path.return_value = self.tmpdir
            self.assertTrue(ngx_conf.write('site1.local', conf))
            # Write again with same contents
            self.assertFalse(ngx_conf.write('site1.local', conf))
        with open(os.path.join(self.tmpdir, 'site1.local'), 'rb') as f:
            output = f.read().decode('utf-8')
        self.assertEqual(conf, output)


if __name__ == '__main__':
    unittest.main()
