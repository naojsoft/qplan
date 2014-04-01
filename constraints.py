#
# constraints.py -- scheduling constraints
#
#  Eric Jeschke (eric@naoj.org)
#
import misc

class Constraints(object):
    
    def __init__(self, available_filters=None, start_time=None):
        self.available_filters = available_filters
        self.start_time = start_time
    
    def cns_correct_filters(self, slot, msb):
        """
        Make sure there are no filters specified by this program that
        are not available.
        """
        return msb.filter in self.available_filters

    def cns_target_observable(self, slot, msb):
        """
        Make sure that the target specified is viewable with the
        program's desired elevation constraints.
        """

        time1 = slot.start_time
        time2 = slot.stop_time
        tgt = msb.target
        body = tgt.get_body()
        return misc.observable(body, time1, time2, 15.0, 85.0)
        
        return True


