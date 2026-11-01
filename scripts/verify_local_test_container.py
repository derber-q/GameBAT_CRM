"""Приёмка уже запущенного local_test: Docker-границы проверяются без Django-guard."""
import argparse
import http.client
import ipaddress
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def docker(*args, input=None):
    return subprocess.run(['docker', *args], input=input, text=True, encoding='utf-8',
                          capture_output=True, check=True, timeout=45).stdout


def verify(project, live_ip):
    compose = ('compose', '-p', project, '-f', str(ROOT/'deploy/local_test/compose.yaml'))
    crm_id = docker(*compose, 'ps', '-q', 'crm-test').strip()
    ingress_id = docker(*compose, 'ps', '-q', 'ingress').strip()
    assert crm_id and ingress_id, 'Нужны оба запущенных контейнера.'
    crm, ingress = [json.loads(docker('inspect', value))[0] for value in (crm_id, ingress_id)]
    for item, uid in ((crm, '10001:10001'), (ingress, '101:101')):
        assert item['State']['Running']
        assert item['Config']['User'] == uid
        assert item['HostConfig']['ReadonlyRootfs']
        assert item['HostConfig']['CapDrop'] == ['ALL']
        assert 'no-new-privileges:true' in item['HostConfig']['SecurityOpt']
        assert not item['HostConfig']['Privileged']
        assert all(mount['Type'] in ('volume', 'tmpfs') for mount in item['Mounts'])
    assert len(crm['Mounts']) == 1
    assert crm['HostConfig']['Init'] is True
    assert crm['Mounts'][0]['Destination'] == '/app/outputs/local_test'
    assert not ingress['Mounts']
    networks = crm['NetworkSettings']['Networks']
    assert len(networks) == 1
    name, endpoint = next(iter(networks.items()))
    network = json.loads(docker('network', 'inspect', name))[0]
    assert network['Internal']
    assert network['Options']['com.docker.network.bridge.gateway_mode_ipv4'] == 'isolated'
    assert not endpoint['Gateway']
    assert set(ingress['NetworkSettings']['Networks']) == {name, project+'_entry'}
    assert not crm['HostConfig']['PortBindings']
    assert ingress['NetworkSettings']['Ports'] == {
        '8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8002'}]}
    assert not network['IPAM']['Config'][0].get('Gateway')
    entry = json.loads(docker('network', 'inspect', project+'_entry'))[0]
    bridge_ip = entry['IPAM']['Config'][0]['Gateway']
    # Этот новый Python-процесс не импортирует приложение и не устанавливает audit hooks.
    probe = '''
import errno, json, os, socket, sys
from pathlib import Path
assert 'django' not in sys.modules
socket.setdefaulttimeout(2)
result = {}
for host, port in TARGETS:
    try:
        with socket.create_connection((host,port),timeout=2): pass
    except OSError as error:
        # ECONNREFUSED означает достижимый узел без listener, а не сетевую изоляцию.
        assert error.errno != errno.ECONNREFUSED, (host, port, str(error))
        result[f'{host}:{port}'] = str(error)
    else: raise AssertionError(f'Внешнее соединение разрешено: {host}:{port}')
try: socket.getaddrinfo('example.com',443)
except socket.gaierror: result['external_dns'] = 'blocked'
else: raise AssertionError('Внешний DNS доступен')
assert not any(line.split()[1]=='00000000' for line in Path('/proc/net/route').read_text().splitlines()[1:])
assert os.getuid()==10001
status=Path('/proc/self/status').read_text()
assert 'CapEff:\\t0000000000000000' in status
assert 'NoNewPrivs:\\t1' in status
for path in ['/app/db.sqlite3','/app/protected_media','/app/backups','/var/run/docker.sock',
             '/app/.env','/app/.integration-encryption-key']:
    assert not Path(path).exists(), path
try: Path('/app/.isolation-probe').write_text('must be read-only')
except OSError as error: assert error.errno==errno.EROFS, error
else: raise AssertionError('Исходники доступны для записи')
result['no_django_guard'] = True
result['read_only_and_unprivileged'] = True
print(json.dumps(result))
'''
    targets = [('1.1.1.1', 443), (live_ip, 8000),
               ('host.docker.internal', 8000), (bridge_ip, 8000), (bridge_ip, 53)]
    raw = docker(*compose, 'exec', '-T', 'crm-test', 'python', '-',
                 input='TARGETS = '+repr(targets)+'\n'+probe)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic()+90
    while True:
        try:
            with opener.open('http://127.0.0.1:8002/crm/accounts/login/', timeout=3) as response:
                assert response.status == 200
                assert response.headers.get('X-GameBAT-Environment') == 'local_test'
                assert 'ТЕСТОВЫЙ РЕЖИМ' in response.read().decode('utf-8')
            break
        except (OSError, urllib.error.URLError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    # Ни absolute URI, ни CONNECT не превращают входной прокси в выходной HTTP-прокси.
    connection = http.client.HTTPConnection('127.0.0.1', 8002, timeout=3)
    try:
        connection.request('GET', 'http://example.com/crm/accounts/login/',
                           headers={'Host': '127.0.0.1:8002'})
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader('X-GameBAT-Environment') == 'local_test'
        response.read()
    finally:
        connection.close()
    request = urllib.request.Request('http://127.0.0.1:8002/', method='CONNECT')
    try: opener.open(request, timeout=3)
    except urllib.error.HTTPError as error: assert error.code in (400, 405)
    else: raise AssertionError('CONNECT не отклонён')
    return {'project': project, 'http_login': 200, 'docker_boundaries': 'passed',
            'raw_network_probe': json.loads(raw)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--live-ip', required=True, type=ipaddress.IPv4Address)
    args = parser.parse_args()
    print(json.dumps(verify(args.project, str(args.live_ip)), ensure_ascii=False, indent=2))
