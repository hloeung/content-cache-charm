import datetime
import hashlib
import hmac
import os
import re
import shutil
import subprocess


BASE_CACHE_PORT = 6080
BASE_BACKEND_PORT = 8080
BACKEND_PORT_LIMIT = 61000  # sysctl net.ipv4.ip_local_port_range


class InvalidPortError(Exception):
    pass


class InvalidAddressPortError(Exception):
    pass


class InvalidTLSCiphersError(Exception):
    pass


def next_port_pair(
    cache_port,
    backend_port,
    base_cache_port=BASE_CACHE_PORT,
    base_backend_port=BASE_BACKEND_PORT,
    backend_port_limit=BACKEND_PORT_LIMIT,
    blacklist_ports=None,
):
    if blacklist_ports is None:
        blacklist_ports = []

    if cache_port == 0:
        cache_port = base_cache_port
    else:
        cache_port += 1
    while cache_port in blacklist_ports:
        cache_port += 1

    if backend_port == 0:
        backend_port = base_backend_port
    else:
        backend_port += 1
    while backend_port in blacklist_ports:
        backend_port += 1

    if cache_port < base_cache_port or cache_port >= base_backend_port:
        raise InvalidPortError('Dynamically allocated cache_port out of range')

    port_limit = base_backend_port + (base_backend_port - base_cache_port)
    if port_limit >= backend_port_limit:
        port_limit = backend_port_limit

    if backend_port < base_backend_port or backend_port >= port_limit:
        raise InvalidPortError('Dynamically allocated backend_port out of range')

    return (cache_port, backend_port)


def _nagios_check_name_strip(name):
    return name.replace('.', '_').replace('-', '_').replace('/', '').replace('__', '_').strip('_')


def generate_nagios_check_name(name, prefix='', suffix=''):
    check_name = name
    if prefix:
        check_name = '{}_{}'.format(prefix, check_name)
    if suffix:
        check_name = '{}_{}'.format(check_name, suffix)
    return _nagios_check_name_strip(check_name)


def generate_token(signing_secret, url_path, expiry_time):
    expiration = int(expiry_time.timestamp())
    string_to_sign = "{0}{1}".format(url_path, expiration)
    digest = hmac.new(signing_secret.encode(), string_to_sign.encode(), hashlib.sha1)
    return "{0}_{1}".format(expiration, digest.hexdigest())


def never_expires_time():
    dt = datetime.date(datetime.datetime.now().year, 1, 1)
    tm = datetime.time(00, 00)
    expiry_time = datetime.datetime.combine(dt, tm) + datetime.timedelta(days=3653)
    return expiry_time


def generate_uri(host, port=80, path=None, scheme='http'):
    if not path:
        path = ''
    # XXX: Fix to handle if host is an IPv6 literal
    if path and not path.startswith('/'):
        path = '/{}'.format(path)
    uri = '{scheme}://{host}:{port}{path}'.format(scheme=scheme, host=host, port=port, path=path)
    return uri


def cache_max_size(path, percent=75):
    total = shutil.disk_usage(path)[0]
    percent = percent / 100
    gbytes = 1024 * 1024 * 1024
    return '{}g'.format(max(1, int((total * percent) / gbytes)))


def ip_addr_port_split(addr_port):
    addr = None

    # IPv4
    regex = re.compile('((\\d{1,3}).(\\d{1,3}).(\\d{1,3}).(\\d{1,3})):(\\d{1,5})')
    m = regex.match(addr_port)
    if m:
        addr, port = m.group(1, 6)
        for octet in m.group(2, 3, 4, 5):
            if int(octet) > 255:
                addr = None
                break

    # IPv6
    else:
        regex = re.compile('\\[([:a-fA-F0-9]+)\\]:(\\d{1,5})')
        m = regex.match(addr_port)
        if m:
            addr, port = m.group(1, 2)
        else:
            port = addr_port.split(':')[-1]

    port = int(port)
    if port > 65535:
        port = None

    if addr is None or port is None:
        raise InvalidAddressPortError('Unable to split IP address and port from "{}"'.format(addr_port))

    return (addr, port)


def tls_cipher_suites(tls_cipher_suites):
    cmd = ['openssl', 'ciphers', '--', tls_cipher_suites]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        raise InvalidTLSCiphersError('Unable to parse provided OpenSSL cipher string "{}"'.format(tls_cipher_suites))
    return tls_cipher_suites


def logrotate(path, retention=30, dateext=True):
    if not os.path.exists(path):
        return None

    with open(path, 'r', encoding='utf-8') as f:
        config = f.read().split('\n')

    new = []
    regex = re.compile('^(\\s+)(rotate|dateext)')
    for line in config:
        m = regex.match(line)
        if m:
            if m.group(2) == 'dateext':
                continue
            if dateext:
                new.append('{}dateext'.format(m.group(1)))
            new.append('{}rotate {}'.format(m.group(1), retention))
        else:
            new.append(line)

    return '\n'.join(new)


LIMITS_MATCH = {
    'NOFILE': 'Max open files',
}


def process_rlimits(pid, res, limits_file=None):
    if not limits_file:
        limits_file = os.path.join('/proc', str(pid), 'limits')

    if not os.path.exists(limits_file):
        return None

    with open(limits_file, 'r', encoding='utf-8') as f:
        limits = f.read()

    if res not in LIMITS_MATCH:
        return None

    r = re.compile(r'^{}\s+\S+\s+(\S+)'.format(LIMITS_MATCH[res]))
    for line in limits.split('\n'):
        m = r.match(line)
        if m:
            return m.group(1)

    return None
