import unittest
import math
from dateutil import tz

from qplan import misc, entity, qsim
from qplan.util import calcpos


        # RA           DEC          EQ
vega = ("18:36:56.3", "+38:47:01", "2000")
altair = ("19:51:29.74", "8:54:23.5", "2000")

class TestEntity01(unittest.TestCase):

    def setUp(self):
        self.hst = tz.gettz('US/Hawaii')
        self.utc = tz.UTC
        self.obs = entity.Observer('subaru',
                                   longitude='-155:28:48.900',
                                   latitude='+19:49:42.600',
                                   elevation=4163,
                                   pressure=615,
                                   temperature=0,
                                   timezone=self.hst)

    def tearDown(self):
        pass

    def test_get_date(self):
        time1 = self.obs.get_date("2014-04-15 19:00")
        time2 = self.obs.get_date("2014-04-15 20:00")
        self.assertTrue(time1 < time2)

    def test_get_body(self):
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        self.assertTrue(isinstance(tgt.body, calcpos.Body))

    def test_observable_1(self):
        # vega should be visible during this period
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-29 04:00")
        time2 = self.obs.get_date("2014-04-29 05:00")
        is_obs, time_rise, time_set = qsim.observable(self.obs, tgt,
                                                      time1, time2,
                                                      15.0, 85.0,
                                                      59.9*60)
        print((1, is_obs, time_rise, time_set))
        self.assertTrue(is_obs == True)

    def test_observable_2(self):
        # vega should be visible near the end but not in the beginning
        # during this period (rising)
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-28 22:00")
        time2 = self.obs.get_date("2014-04-28 23:00")
        is_obs, time_rise, time_set = qsim.observable(self.obs, tgt,
                                                      time1, time2,
                                                      15.0, 85.0,
                                                      60*15)  # 15 min ok
        print((2, is_obs, time_rise, time_set))
        self.assertTrue(is_obs == True)

    def test_observable_3(self):
        # vega should be visible near the end but not in the beginning
        # during this period (rising)
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-28 22:00")
        time2 = self.obs.get_date("2014-04-28 23:00")
        is_obs, time_rise, time_set = qsim.observable(self.obs, tgt,
                                                      time1, time2,
                                                      15.0, 85.0,
                                                      60*16)  # 16 min NOT ok
        print((3, is_obs, time_rise, time_set))
        self.assertTrue(is_obs == False)

    def test_observable_4(self):
        # vega should be visible near the beginning but not near the end
        # during this period (setting)
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-29 10:00")
        time2 = self.obs.get_date("2014-04-29 11:00")
        is_obs, time_rise, time_set = qsim.observable(self.obs, tgt,
                                                      time1, time2,
                                                      15.0, 85.0,
                                                      60*14)  # 14 min ok
        print((4, is_obs, time_rise, time_set))
        self.assertTrue(is_obs == True)

    def test_observable_5(self):
        # vega should be visible near the beginning but not near the end
        # during this period (setting)
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-29 10:00")
        time2 = self.obs.get_date("2014-04-29 11:00")
        is_obs, time_rise, time_set = qsim.observable(self.obs, tgt,
                                                      time1, time2,
                                                      15.0, 85.0,
                                                      60*15)  # 15 min NOT ok
        print((5, is_obs, time_rise, time_set))
        self.assertTrue(is_obs == False)

    def test_observable_6(self):
        # vega should be visible near the beginning but not near the end
        # during this period (setting)
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-29 11:00")
        time2 = self.obs.get_date("2014-04-29 12:00")
        is_obs, time_rise, time_set = qsim.observable(self.obs, tgt,
                                                      time1, time2,
                                                      15.0, 85.0,
                                                      60*1)  # 1 min NOT ok
        print((6, is_obs, time_rise, time_set))
        self.assertTrue(is_obs == False)

    def ftest_airmass(self):
        # calculate airmass via "observer" module
        import observer
        obs = observer.Observer('subaru')
        obs.almanac('2010/10/18')
        tgt = observer.tools.Target('ACTJ0022-0036',
                                    '00:22:13.44', '-00:36:25.20')
        am = observer.tools.Airmass(obs.almanac_data, tgt)
        time1 = self.obs.get_date("2010-10-18 22:00")
        time1_ut = time1.astimezone(tz.UTC)
        tup = am.compute_one(tgt.target, time1_ut)
        amass = tup[4]

        # now calculate via misc
        body = entity.StaticTarget('ACTJ0022-0036',
                                   '00:22:13.44', '-00:36:25.20')
        time1 = self.obs.get_date("2010-10-18 22:00")
        c1 = self.obs.calc(body, time1)
        self.assertTrue(math.fabs(amass - c1.airmass) < 0.01)

    def test_airmass2(self):
        # now calculate via misc
        body = entity.StaticTarget('ACTJ0022-0036',
                                   '00:22:13.44', '-00:36:25.20')
        time1 = self.obs.get_date("2010-10-18 21:00")
        c1 = self.obs.calc(body, time1)
        self.assertTrue(c1.airmass > 1.2)

    ## def test_airmass3(self):
    ##     # now calculate via misc
    ##     body = entity.StaticTarget('ACTJ0022-0036',
    ##                                '00:22:13.44', '-00:36:25.20')
    ##     time1 = self.obs.get_date("2010-10-18 19:00")
    ##     for i in xrange(0, 60*8, 5):
    ##         off = timedelta(seconds=i*60)
    ##         time = time1 + off
    ##         c1 = self.obs.calc(body, time)
    ##         print("%s  %s  %f" % (c1.lt.strftime("%H:%M"),
    ##                               c1.ut.strftime("%H:%M"), c1.airmass))

    def test_slot_split(self):
        time1 = self.obs.get_date("2010-10-18 21:00")
        time2 = self.obs.get_date("2010-10-18 21:30")
        # 2 hr slot
        slot = entity.Slot(time1, 3600.0 * 2)
        res = slot.split(time2, 3600.0)
        self.assertTrue(res[0].stop_time == time2)

    def test_distance_1(self):
        tgt1 = entity.StaticTarget("vega", vega[0], vega[1])
        tgt2 = entity.StaticTarget("altair", altair[0], altair[1])
        time1 = self.obs.get_date("2010-10-18 22:00")
        d_alt, d_az = self.obs.distance(tgt1, tgt2, time1)
        self.assertEqual(int(math.fabs(d_alt)), 11)
        self.assertEqual(int(math.fabs(d_az)), 38)

    def test_calc_alternate_angle(self):
        res = misc.calc_alternate_angle(0.0)
        self.assertEqual(int(res), 0)
        res = misc.calc_alternate_angle(20.0)
        self.assertEqual(int(res), -340)
        res = misc.calc_alternate_angle(90.0)
        self.assertEqual(int(res), -270)
        res = misc.calc_alternate_angle(177.0)
        self.assertEqual(int(res), -183)
        res = misc.calc_alternate_angle(180.0)
        self.assertEqual(int(res), -180)
        res = misc.calc_alternate_angle(270.0)
        self.assertEqual(int(res), -90)
        res = misc.calc_alternate_angle(1.0)
        self.assertEqual(int(res), -359)

    def test_calc_rotation_choices1(self):
        pass

    def test_calc_rotation_choices2(self):
        pass

    def test_calc_optimal_rotation(self):
        pass

if __name__ == "__main__":

    print('\n>>>>> Starting test_misc <<<<<\n')
    unittest.main()
