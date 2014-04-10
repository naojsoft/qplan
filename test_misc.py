import unittest
from datetime import timedelta
import math
import pytz

import ephem

import misc
import entity


        # RA           DEC          EQ
vega = ("18:36:56.3", "+38:47:01", "2000")

class TestTask01(unittest.TestCase):

    def setUp(self):
        self.hst = entity.HST()
        self.utc = pytz.utc
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
        self.assert_(time1 < time2)
    
    def test_get_body(self):
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        self.assert_(isinstance(tgt.body, ephem.Body))
    
    def test_observable_1(self):
        # vega should be visible during this period
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-29 04:00")
        time2 = self.obs.get_date("2014-04-29 05:00")
        is_obs = self.obs.observable(tgt, time1, time2, 15.0, 85.0)
        self.assert_(is_obs == True)
    
    def test_observable_2(self):
        # vega should be visible near the end but not in the beginning
        # during this period
        tgt = entity.StaticTarget("vega", vega[0], vega[1])
        time1 = self.obs.get_date("2014-04-28 22:00")
        time2 = self.obs.get_date("2014-04-28 23:00")
        is_obs = self.obs.observable(tgt, time1, time2, 15.0, 85.0)
        self.assert_(is_obs == False)
    
    def test_airmass(self):
        # calculate airmass via "observer" module
        import observer
        obs = observer.Observer('subaru')
        obs.almanac('2010/10/18')
        tgt = observer.tools.Target('ACTJ0022-0036',
                                    '00:22:13.44', '-00:36:25.20')
        am = observer.tools.Airmass(obs.almanac_data, tgt)
        time1 = self.obs.get_date("2010-10-18 22:00")
        time1_ut = time1.astimezone(pytz.utc)
        tup = am.compute_one(tgt.target, time1_ut)
        amass = tup[4]

        # now calculate via misc
        body = entity.StaticTarget('ACTJ0022-0036',
                                   '00:22:13.44', '-00:36:25.20')
        time1 = self.obs.get_date("2010-10-18 22:00")
        c1 = self.obs.calc(body, time1)
        self.assert_(math.fabs(amass - c1.airmass) < 0.01)
    
    def test_airmass2(self):
        # now calculate via misc
        body = entity.StaticTarget('ACTJ0022-0036',
                                   '00:22:13.44', '-00:36:25.20')
        time1 = self.obs.get_date("2010-10-18 21:00")
        c1 = self.obs.calc(body, time1)
        self.assert_(c1.airmass > 1.2)
    
    ## def test_airmass3(self):
    ##     # now calculate via misc
    ##     body = entity.StaticTarget('ACTJ0022-0036',
    ##                                '00:22:13.44', '-00:36:25.20')
    ##     time1 = self.obs.get_date("2010-10-18 19:00")
    ##     for i in xrange(0, 60*8, 5):
    ##         off = timedelta(0, i*60)
    ##         time = time1 + off
    ##         c1 = self.obs.calc(body, time)
    ##         print "%s  %s  %f" % (c1.lt.strftime("%H:%M"),
    ##                               c1.ut.strftime("%H:%M"), c1.airmass)
    

if __name__ == "__main__":

    print '\n>>>>> Starting test_misc <<<<<\n'
    unittest.main()
