import types
import sys
import pytest

# Minimal fake weeutil module
weeutil = types.SimpleNamespace()

def to_bool(val):
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).lower()
    return s in ("1", "true", "yes", "on")

weeutil.weeutil = types.SimpleNamespace(to_bool=to_bool, latlon_string=lambda v, dirs, kind: ("N",))

# Minimal fake weewx package
weewx = types.SimpleNamespace()
weewx_engine = types.SimpleNamespace()

# Top-level event constant expected by APRS
weewx.NEW_ARCHIVE_RECORD = 'NEW_ARCHIVE_RECORD'


class FakeConfig:
    """Simple config wrapper providing get(section, option, default=None).

    The test fixtures pass a plain mapping like {
        'APRS': { 'output_filename': ..., ... }
    } and the APRS service expects to be able to call
    self.config.get('APRS', 'push_url'). This wrapper adapts a dict to
    that API for tests.
    """
    def __init__(self, mapping):
        self._m = mapping or {}

    def get(self, section, option, default=None):
        sec = self._m.get(section, {})
        # sec may be a dict-like mapping
        return sec.get(option, default)

    # Make FakeConfig subscriptable like a mapping: service.config['APRS'] -> dict
    def __getitem__(self, section):
        return self._m.setdefault(section, {})

    def __setitem__(self, section, value):
        self._m[section] = value

class DummyStdService:
    def __init__(self, engine, config_dict):
        # expose config like real StdService
        # wrap the provided mapping with FakeConfig so calls to
        # self.config.get(section, option) work in tests
        self.config = FakeConfig(config_dict)
        self.engine = engine
        # simple storage for bound events (tests can ignore)
        self._bindings = {}

    def bind(self, event, handler):
        """Minimal bind implementation used by APRS during tests."""
        self._bindings.setdefault(event, []).append(handler)

weewx.engine = types.SimpleNamespace(StdService=DummyStdService, NEW_ARCHIVE_RECORD='NEW_ARCHIVE_RECORD')
weewx.units = types.SimpleNamespace(convert=lambda x, y: (x[0],))

# Insert these into sys.modules so the code under test can import them
sys.modules['weeutil'] = weeutil
sys.modules['weeutil.weeutil'] = weeutil.weeutil
sys.modules['weewx'] = weewx
sys.modules['weewx.engine'] = weewx.engine
sys.modules['weewx.units'] = weewx.units

# Provide a small fake engine object used by APRS
class FakeEngine:
    def __init__(self):
        self.stn_info = types.SimpleNamespace(latitude_f=37.0, longitude_f=-122.0)


@pytest.fixture
def fake_engine():
    return FakeEngine()


@pytest.fixture
def basic_config(tmp_path):
    # create a minimal config structure like the real weewx config
    conf = {
        'APRS': {
            'output_filename': str(tmp_path / 'aprs.out'),
            'station_model': 'testmodel',
            'include_position': '0',
            'report_luminosity': '0',
        }
    }
    return conf
