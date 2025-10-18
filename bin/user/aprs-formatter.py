from datetime import datetime, timezone
import os
import requests

import weeutil.weeutil
import weewx.engine
import weewx.units
import logging


class APRS(weewx.engine.StdService):
    """APRS packet formatter service for WeeWX.

    Responsibilities:
    - build APRS weather packets from archive records
    - write the packet to a local file (atomic replace)
    - optionally push the packet to a remote HTTP endpoint

    Config keys (in the `APRS` section):
    - output_filename (required)
    - include_position (0/1)
    - symbol_table, symbol_code, comment
    - station_model
    - report_luminosity (0/1)
    - push_url, push_enabled, push_user, push_password, push_ssl_verify
    """

    def __init__(self, engine, config_dict):
        super(APRS, self).__init__(engine, config_dict)
        conf = config_dict['APRS']
        self._output_filename = conf['output_filename']
        self._output_filename_tmp = self._output_filename + '.tmp'
        self._include_position = int(conf.get('include_position', 0))
        self._symbol_table = conf.get('symbol_table', '/')
        self._symbol_code = conf.get('symbol_code', '_')
        self._comment = conf.get('comment', '')
        self._stationModel = conf['station_model']
        self._reportLuminosity =  int(conf.get('report_luminosity', 0))

        self._message_type = '_'  # Weather report (no position)
        self._time_format = '%m%d%H%M'
        self._latitude = None
        self._longitude = None
        
        # Accurite model 01036 seems to require these markers with no timestamp
        if "accurite" in self._stationModel:
            self._wind_direction_marker = ''
            self._wind_speed_marker = '/'
        else:
            self._wind_direction_marker = 'c'
            self._wind_speed_marker = 's'
        
        if self._include_position:
            # Position with timestamp (no APRS messaging)
            self._message_type = '/'
            self._time_format = '%d%H%Mz'
            self._latitude = ''.join(weeutil.weeutil.latlon_string(
                self.engine.stn_info.latitude_f,
                ('N', 'S'), 'lat'))
            self._longitude = ''.join(weeutil.weeutil.latlon_string(
                self.engine.stn_info.longitude_f,
                ('E', 'W'), 'lon'))
            self._wind_direction_marker = ''
            self._wind_speed_marker = '/'

        self.bind(weewx.NEW_ARCHIVE_RECORD, self._handle_new_archive_record)

    def _handle_new_archive_record(self, event):
        """Generate a positionless APRS weather report and write it to a file.

        This method delegates numeric formatting to helper methods to keep
        behavior predictable and easy to test.
        """

        record = event.record

        # Start packet header: message type + optional timestamp
        if "accurite" in self._stationModel:
            parts = [self._message_type, '']
        else:
            ts = datetime.fromtimestamp(record['dateTime'], timezone.utc)
            parts = [self._message_type, datetime.strftime(ts, self._time_format)]

        # include position when configured
        if self._include_position:
            parts.extend([self._latitude, self._symbol_table, self._longitude, self._symbol_code])

        # Wind direction
        parts.append(self._format_wind_dir(record.get('windDir')))

        # Wind speed
        parts.append(self._format_wind_speed(record.get('windSpeed')))

        # Wind gust
        parts.append(self._format_wind_gust(record.get('windGust')))

        # Temperature
        parts.append(self._format_temperature(record.get('outTemp')))

        # Rain rates
        parts.append(self._format_rain_rate(record.get('rainRate')))
        parts.append(self._format_rain_24h(record.get('rain24h')))
        parts.append(self._format_day_rain(record.get('dayRain')))

        # Humidity
        hum = self._format_humidity(record.get('outHumidity'))
        if hum:
            parts.append(hum)

        # Barometer
        bar = self._format_barometer(record.get('barometer'))
        if bar:
            parts.append(bar)

        # Luminosity
        if self._reportLuminosity == 1:
            lum = self._format_luminosity(record.get('luminosity'))
            if lum:
                parts.append(lum)

        if self._comment:
            parts.append(self._comment)

        wxdata = ''.join(parts)

        # write atomically and push
        self._write_output(wxdata)
        self.push_packet(wxdata)

    # --- helper formatting methods ---
    def _format_wind_dir(self, wind_dir_raw):
        if wind_dir_raw is None:
            return f"{self._wind_direction_marker}000"
        try:
            wind_dir = int(round(wind_dir_raw))
            if wind_dir <= 0:
                wind_dir = 360
            return f"{self._wind_direction_marker}{wind_dir:03d}"
        except Exception:
            logging.exception("format wind_dir failed")
            return f"{self._wind_direction_marker}000"

    def _format_wind_speed(self, wind_speed_raw):
        if wind_speed_raw is None:
            return f"{self._wind_speed_marker}..."
        try:
            speed = int(round(wind_speed_raw))
            return f"{self._wind_speed_marker}{speed:03d}"
        except Exception:
            logging.exception("format wind_speed failed")
            return f"{self._wind_speed_marker}..."

    def _format_wind_gust(self, gust_raw):
        if gust_raw is None:
            return 'g...'
        try:
            gust = int(round(gust_raw))
            return f"g{gust:03d}"
        except Exception:
            logging.exception("format gust failed")
            return 'g...'

    def _format_temperature(self, temp_raw):
        if temp_raw is None:
            return 't...'
        try:
            t = int(round(temp_raw))
            return f"t{t:03d}"
        except Exception:
            logging.exception("format temperature failed")
            return 't...'

    def _format_rain_rate(self, rain_raw):
        if rain_raw is None:
            return 'r...'
        try:
            r = int(round(rain_raw * 100))
            return f"r{r:03d}"
        except Exception:
            logging.exception("format rain_rate failed")
            return 'r...'

    def _format_rain_24h(self, rain24_raw):
        if rain24_raw is None:
            return 'p...'
        try:
            p = int(round(rain24_raw * 100))
            return f"p{p:03d}"
        except Exception:
            logging.exception("format rain24h failed")
            return 'p...'

    def _format_day_rain(self, day_raw):
        if day_raw is None:
            return 'P...'
        try:
            P = int(round(day_raw * 100))
            return f"P{P:03d}"
        except Exception:
            logging.exception("format dayRain failed")
            return 'P...'

    def _format_humidity(self, hum_raw):
        if hum_raw is None:
            return None
        try:
            humidity = int(round(hum_raw))
            if humidity >= 100:
                humidity = 0
            return f"h{humidity:02d}"
        except Exception:
            logging.exception("format humidity failed")
            return None

    def _format_barometer(self, baro_raw):
        if baro_raw is None:
            return None
        try:
            # convert from inHg to mbar then to tenths
            barometer = weewx.units.convert((baro_raw, 'inHg', 'pressure'), 'mbar')[0] * 10
            b = int(round(barometer))
            return f"b{b:05d}"
        except Exception:
            logging.exception("format barometer failed")
            return None

    def _format_luminosity(self, lumen_raw):
        if lumen_raw is None:
            return None
        try:
            lumen = int(round(lumen_raw))
            return f"L{lumen:03d}"
        except Exception:
            logging.exception("format luminosity failed")
            return None

    def _write_output(self, wxdata: str) -> None:
        """Atomically write the generated packet to the configured output file."""
        try:
            with open(self._output_filename_tmp, 'w', encoding='utf-8') as f:
                f.write(wxdata)
            logging.info("weewx-aprs-packet-formatter - %s", wxdata)
            os.replace(self._output_filename_tmp, self._output_filename)
        except Exception:
            logging.exception("weewx-aprs-packet-formatter - failed to write output file")

    def push_packet(self, packet_content):
        """
        Pushes the generated APRS packet content to a remote HTTP/HTTPS endpoint.
        """
        # Get configuration settings from self.config (StdService provides this)
        url = self.config.get('APRS', 'push_url')
        enabled = weeutil.weeutil.to_bool(self.config.get('APRS', 'push_enabled', 'False'))
        username = self.config.get('APRS', 'push_user')
        password = self.config.get('APRS', 'push_password')
        verify_ssl = weeutil.weeutil.to_bool(self.config.get('APRS', 'push_ssl_verify', 'True'))

        if not enabled:
            logging.debug("APRS push is disabled in configuration")
            return

        if not url:
            logging.error("APRS push is enabled but 'push_url' is not set.")
            return
        
        logging.info("Attempting to push APRS packet to %s", url)

        # Prepare authentication payload
        auth = (username, password) if username and password else None
        
        # Requests will automatically handle http vs https and the port
        try:
            response = requests.post(
                url,
                data=packet_content,
                auth=auth,
                verify=verify_ssl,
                timeout=10,  # Set a timeout for the request
            )
            response.raise_for_status()  # Raise exception for bad status codes (4xx or 5xx)

            logging.info("APRS packet successfully pushed. Status: %s", response.status_code)

        except requests.exceptions.RequestException as e:
            logging.error("Failed to push APRS packet to %s: %s", url, e)


    def do_format(self, packet, time_ts):
        """
        Formats the packet and then calls the push function.
        """
        # ... (Your existing formatting logic to create the packet_content) ...
        
        # 1. Format the packet
        packet_content = self.do_format_base(packet, time_ts)
        
        # 2. Write to the local file (existing logic)
        self.write_file(packet_content)

        # 3. PUSH the packet (NEW STEP)
        self.push_packet(packet_content)