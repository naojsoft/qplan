import pytest
import numpy as np

from qplan.util import calcpos, site

def get_observer(site_name, date):
    observer = site.get_site(site_name)
    dt = observer.get_date(date)
    observer.set_date(dt)
    return observer


class TestCalcpos_Almanac:

    almanac_limit = 60

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-09 18:48:57 HST")])
    def test_sunset(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        sunset_calc = observer.sunset()
        diff = abs((sunset_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("sunset times differ: {} vs. {}".format(
                sunset_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-09 19:02:19 HST")])
    def test_evening6(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        evening6_calc = observer.evening_twilight_6()
        diff = abs((evening6_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("evening6 times differ: {} vs. {}".format(
                evening6_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-09 19:28:06 HST")])
    def test_evening12(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        evening12_calc = observer.evening_twilight_12()
        diff = abs((evening12_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("evening12 times differ: {} vs. {}".format(
                evening12_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-09 19:54:30 HST")])
    def test_evening18(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        evening18_calc = observer.evening_twilight_18()
        diff = abs((evening18_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("evening18 times differ: {} vs. {}".format(
                evening18_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-10 04:51:28 HST")])
    def test_morning18(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        morning18_calc = observer.morning_twilight_18()
        diff = abs((morning18_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("morning18 times differ: {} vs. {}".format(
                morning18_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-10 05:17:51 HST")])
    def test_morning12(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        morning12_calc = observer.morning_twilight_12()
        diff = abs((morning12_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("morning12 times differ: {} vs. {}".format(
                morning12_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-10 05:43:38 HST")])
    def test_morning6(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        morning6_calc = observer.morning_twilight_6()
        diff = abs((morning6_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("morning6 times differ: {} vs. {}".format(
                morning6_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-10 05:57:00 HST")])
    def test_sunrise(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        sunrise_calc = observer.sunrise()
        diff = abs((sunrise_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("sunrise times differ: {} vs. {}".format(
                sunrise_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-10 07:23:46 HST")])
    def test_moonrise(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        moonrise_calc = observer.moon_rise()
        diff = abs((moonrise_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("moonrise times differ: {} vs. {}".format(
                moonrise_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-09 20:15:57 HST")])
    def test_moonset(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        moonset_calc = observer.moon_set()
        diff = abs((moonset_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("moonset times differ: {} vs. {}".format(
                moonset_calc, expected))

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", .02)])
    def test_moon_illumination(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        moon_illum_calc = observer.moon_illumination()
        assert np.isclose(moon_illum_calc, expected, atol=1.0), \
            Exception("moon illumination differs: {} vs. {}".format(
                moon_illum_calc, moon_illumination)
            )

    @pytest.mark.parametrize(
        ("site_name", "date", "expected"),
        [("subaru", "2024-04-09 12:00 HST", "2024-04-10 00:22:59 HST")])
    def test_night_center(self, site_name, date, expected):
        observer = get_observer(site_name, date)
        expected = observer.get_date(expected)
        night_center_calc = observer.night_center()
        diff = abs((night_center_calc - expected).total_seconds())
        # should be within 1 minute
        assert (diff < self.almanac_limit), \
            Exception("night center times differ: {} vs. {}".format(
                night_center_calc, expected))
