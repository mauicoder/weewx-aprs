import importlib.util
import pathlib
import types

import pytest

# load module by path (same approach as other tests)
_mod_path = pathlib.Path(__file__).resolve().parents[1] / 'bin' / 'user' / 'aprs-formatter.py'
spec = importlib.util.spec_from_file_location('aprs_formatter', str(_mod_path))
assert spec is not None, "failed to create spec for aprs_formatter"
aprs_formatter = importlib.util.module_from_spec(spec)
assert spec.loader is not None, "spec.loader is None"
spec.loader.exec_module(aprs_formatter)


class DummyEngine:
    def __init__(self):
        self.stn_info = types.SimpleNamespace(latitude_f=37.0, longitude_f=-122.0)


@pytest.fixture
def aprs_instance(tmp_path):
    conf = {
        'APRS': {
            'output_filename': str(tmp_path / 'aprs.out'),
            'station_model': 'testmodel',
            'include_position': '0',
            'report_luminosity': '1',
        }
    }
    eng = DummyEngine()
    svc = aprs_formatter.APRS(eng, conf)
    return svc


def test_format_wind_dir_none(aprs_instance):
    assert aprs_instance._format_wind_dir(None) == f"{aprs_instance._wind_direction_marker}000"


def test_format_wind_dir_zero(aprs_instance):
    assert aprs_instance._format_wind_dir(0) == f"{aprs_instance._wind_direction_marker}360"


def test_format_wind_dir_valid(aprs_instance):
    assert aprs_instance._format_wind_dir(5.7) == f"{aprs_instance._wind_direction_marker}006"


def test_format_wind_speed_none(aprs_instance):
    assert aprs_instance._format_wind_speed(None) == f"{aprs_instance._wind_speed_marker}..."


def test_format_wind_speed_rounding(aprs_instance):
    assert aprs_instance._format_wind_speed(5.6) == f"{aprs_instance._wind_speed_marker}006"


def test_format_gust_none(aprs_instance):
    assert aprs_instance._format_wind_gust(None) == 'g...'


def test_format_gust_valid(aprs_instance):
    assert aprs_instance._format_wind_gust(12.4) == 'g012'


def test_format_temperature_none(aprs_instance):
    assert aprs_instance._format_temperature(None) == 't...'


def test_format_temperature_valid(aprs_instance):
    assert aprs_instance._format_temperature(21.7) == 't022'


def test_format_rain_rate_none(aprs_instance):
    assert aprs_instance._format_rain_rate(None) == 'r...'


def test_format_rain_rate_valid(aprs_instance):
    assert aprs_instance._format_rain_rate(0.012) == 'r001'


def test_format_rain_24h_none(aprs_instance):
    assert aprs_instance._format_rain_24h(None) == 'p...'


def test_format_day_rain_none(aprs_instance):
    assert aprs_instance._format_day_rain(None) == 'P...'


def test_format_humidity_none(aprs_instance):
    assert aprs_instance._format_humidity(None) is None


def test_format_humidity_100(aprs_instance):
    assert aprs_instance._format_humidity(100.0) == 'h00'


def test_format_barometer_none(aprs_instance):
    assert aprs_instance._format_barometer(None) is None


def test_format_luminosity_none(aprs_instance):
    assert aprs_instance._format_luminosity(None) is None


def test_format_luminosity_valid(aprs_instance):
    assert aprs_instance._format_luminosity(7.2) == 'L007'
