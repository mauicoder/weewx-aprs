import importlib.util
import pathlib
import types
import requests

# load module
_mod_path = pathlib.Path(__file__).resolve().parents[1] / 'bin' / 'user' / 'aprs-formatter.py'
spec = importlib.util.spec_from_file_location('aprs_formatter', str(_mod_path))
assert spec is not None
aprs_formatter = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(aprs_formatter)


class DummyEngine:
    def __init__(self):
        self.stn_info = types.SimpleNamespace(latitude_f=37.0, longitude_f=-122.0)


class DummyResponse:
    def __init__(self, status_code=200, raise_exc: Exception | None = None):
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc


def test_push_retries_succeeds(monkeypatch, tmp_path):
    conf = {'APRS': {'output_filename': str(tmp_path / 'aprs.out'), 'station_model': 'testmodel', 'push_retries': '3', 'push_backoff': '0', 'push_enabled': '1', 'push_url': 'https://example.test/push'}}
    svc = aprs_formatter.APRS(DummyEngine(), conf)

    calls = {'count': 0}

    def fake_post(url, data, auth, verify, timeout):
        calls['count'] += 1
        # fail the first two times, succeed on third
        if calls['count'] < 3:
            return DummyResponse(status_code=500, raise_exc=requests.exceptions.RequestException('server error'))
        return DummyResponse(status_code=201, raise_exc=None)

    # patch the Session.post used by the aprs_formatter module
    monkeypatch.setattr(aprs_formatter.requests.Session, 'post', lambda self, *a, **k: fake_post(*a, **k))

    svc.push_packet('PACKET')

    assert calls['count'] == 3


def test_push_retries_all_fail(monkeypatch, tmp_path):
    conf = {'APRS': {'output_filename': str(tmp_path / 'aprs.out'), 'station_model': 'testmodel', 'push_retries': '2', 'push_backoff': '0', 'push_enabled': '1', 'push_url': 'https://example.test/push'}}
    svc = aprs_formatter.APRS(DummyEngine(), conf)

    calls = {'count': 0}

    def fake_post(url, data, auth, verify, timeout):
        calls['count'] += 1
        return DummyResponse(status_code=500, raise_exc=requests.exceptions.RequestException('server error'))

    monkeypatch.setattr(aprs_formatter.requests.Session, 'post', lambda self, *a, **k: fake_post(*a, **k))

    svc.push_packet('PACKET')

    assert calls['count'] == 2
