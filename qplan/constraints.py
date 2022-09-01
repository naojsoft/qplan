#
# constraints.py -- scheduling constraints
#
#  E. Jeschke
#
from datetime import timedelta

class Constraints(object):

    def __init__(self, observer=None, available_filters=None):
        self.obs = observer
        self.available_filters = available_filters

    def cns_correct_filters(self, slot, ob):
        """
        Make sure there are no filters specified by this OB that
        are not available.
        """
        return ob.filter in self.available_filters


    def cns_target_observable(self, slot, ob):
        """
        Make sure that the target specified is viewable with the
        OB's desired elevation and airmass constraints.
        """

        s_time = slot.start_time
        e_time = slot.stop_time

        min_el, max_el = ob.get_el_minmax()

        (obs_ok, start) = self.obs.observable(ob.target, s_time, e_time,
                                              min_el, max_el, ob.total_time,
                                              airmass=ob.airmass)
        return obs_ok


    ## def cns_time_enough(self, slot, ob):
    ##     """
    ##     Make sure the time taken by the observing block fits the slot.
    ##     """
    ##     time_done = slot.start_time + timedelta(0, ob.total_time)
    ##     return time_done <= slot.stop_time

#END
