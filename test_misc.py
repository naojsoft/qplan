import unittest
import misc

import datetime
import ephem


        # RA           DEC          EQ
vega = ("18:36:56.3", "+38:47:01", "2000")

class TestTask01(unittest.TestCase):

    def setUp(self):
        pass
    
    def tearDown(self):
        pass

    def test_get_date(self):
        time1 = misc.get_date("2014-04-15 19:00")
        time2 = misc.get_date("2014-04-15 20:00")
        self.assert_(time1 < time2)
    
    def test_get_body(self):
        body = misc.get_body("vega", vega[0], vega[1])
        time1 = misc.get_date("2014-04-15 19:00")
        sobs = misc.get_observer(time1)
        body.compute(sobs)
        self.assert_(isinstance(body, ephem.Body))
    
    def test_observable_1(self):
        # vega should be visible during this period
        body = misc.get_body("vega", vega[0], vega[1])
        time1 = misc.get_date("2014-04-29 01:00")
        time2 = misc.get_date("2014-04-29 02:00")
        is_obs = misc.observable(body, time1, time2, 15.0, 85.0)
        self.assert_(is_obs == True)
    
    def test_observable_2(self):
        # vega should be visible near the end but not in the beginning
        # during this period
        body = misc.get_body("vega", vega[0], vega[1])
        time1 = misc.get_date("2014-04-28 22:00")
        time2 = misc.get_date("2014-04-28 23:00")
        is_obs = misc.observable(body, time1, time2, 15.0, 85.0)
        self.assert_(is_obs == False)
    
   

if __name__ == "__main__":

    print '\n>>>>> Starting test_misc <<<<<\n'
    unittest.main()
