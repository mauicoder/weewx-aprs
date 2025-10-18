import os
import types

# Import the aprs-formatter module directly by path (bin is not a package)
import importlib.util
import pathlib

_mod_path = pathlib.Path(__file__).resolve().parents[1] / 'bin' / 'user' / 'aprs-formatter.py'
spec = importlib.util.spec_from_file_location('aprs_formatter', str(_mod_path))
assert spec is not None, "failed to create spec for aprs_formatter"
aprs_formatter = importlib.util.module_from_spec(spec)
assert spec.loader is not None, "spec.loader is None"
spec.loader.exec_module(aprs_formatter)


class DummyEvent:
    def __init__(self, record):
        self.record = record


def test_handle_new_archive_record_basic(fake_engine, basic_config, tmp_path, monkeypatch):
    # instantiate APRS
    service = aprs_formatter.APRS(fake_engine, basic_config)

    # create a simple record
    record = {
        'dateTime': 1600000000,
        'windDir': 45.0,
        'windSpeed': 5.2,
        'windGust': 8.3,
        'outTemp': 68.2,
        'rainRate': 0.01,  # inch/hr
        'rain24h': 0.05,
        'dayRain': 0.02,
        'outHumidity': 55.0,
        'barometer': 29.92,
    }

    ev = DummyEvent(record)

    # Ensure push_packet doesn't actually try network: patch requests.Session.post
    monkeypatch.setattr(aprs_formatter.requests.Session, 'post', lambda self, *a, **k: types.SimpleNamespace(status_code=200, raise_for_status=lambda: None))

    # Call handler
    service._handle_new_archive_record(ev)

    # Check output file exists
    out = basic_config['APRS']['output_filename']
    assert os.path.exists(out)
    content = open(out, 'r', encoding='utf-8').read()
    assert content  # not empty


def test_accurite_branch(fake_engine, basic_config, tmp_path, monkeypatch):
    # set station_model to include accurite
    basic_config['APRS']['station_model'] = 'accurite 01036'
    basic_config['APRS']['include_position'] = '0'

    service = aprs_formatter.APRS(fake_engine, basic_config)

    record = {
        'dateTime': 1600000000,
    }
    ev = DummyEvent(record)

    # Patch requests.Session.post to avoid network
    monkeypatch.setattr(aprs_formatter.requests.Session, 'post', lambda self, *a, **k: types.SimpleNamespace(status_code=200, raise_for_status=lambda: None))

    service._handle_new_archive_record(ev)

    out = basic_config['APRS']['output_filename']
    assert os.path.exists(out)
    content = open(out, 'r', encoding='utf-8').read()
    assert content.startswith('_') or content.startswith('/')


def test_push_packet_calls_requests(fake_engine, basic_config, tmp_path, monkeypatch):
    service = aprs_formatter.APRS(fake_engine, basic_config)

    # enable push and set URL
    service.config['APRS']['push_enabled'] = '1'
    service.config['APRS']['push_url'] = 'https://example.test/push'

    called = {}

    def fake_post(url, data, auth, verify, timeout):
        called['url'] = url
        called['data'] = data
        return types.SimpleNamespace(status_code=201, raise_for_status=lambda: None)

    # patch the Session.post used by the implementation
    monkeypatch.setattr(aprs_formatter.requests.Session, 'post', lambda self, *a, **k: fake_post(*a, **k))

    service.push_packet('TESTPACKET')

    assert called.get('url') == 'https://example.test/push'
    assert called.get('data') == 'TESTPACKET'
