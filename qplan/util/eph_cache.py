from datetime import timedelta
import multiprocessing as mp

import numpy as np
from dateutil import tz

from ginga.misc.Bunch import Bunch

core_count = mp.cpu_count()
_mp_site = None
_mp_cache = None
_mp_dt_arr = None
_mp_tgts = None


class EphemerisCache:

    def __init__(self, logger, precision_minutes=5, columns=None,
                 default_period_check=True):
        self.logger = logger
        self.precision_minutes = precision_minutes
        if columns is None:
            columns = ['lt', 'alt_deg', 'az_deg', 'airmass', 'pang_deg',
                       'moon_alt', 'moon_sep', 'moon_pct']
        self._columns = columns
        self.period_check = default_period_check
        self.vis_catalog = dict()

    def get_target_data(self, key):
        vis_dct = self.vis_catalog.get(key, None)
        return vis_dct

    def clear_target_data(self, key):
        if key in self.vis_catalog:
            del self.vis_catalog[key]

    def clear_all(self):
        self.vis_catalog = dict()

    def get_date_array(self, start_time, stop_time):
        # round start time to every self.interval_min minutes
        int_min = self.precision_minutes
        start_minute = start_time.minute // int_min * int_min
        start_time = start_time.replace(minute=start_minute,
                                        second=0, microsecond=0)
        stop_minute = stop_time.minute // int_min * int_min
        stop_time = stop_time.replace(minute=stop_minute,
                                      second=0, microsecond=0)

        # create date array
        # NOTE: numpy does not like to parse timezone-aware datetimes
        # to np.datetime64
        dt_arr = np.arange(start_time.astimezone(tz.UTC).replace(tzinfo=None),
                           stop_time.astimezone(tz.UTC).replace(tzinfo=None) +
                           timedelta(minutes=int_min),
                           timedelta(minutes=int_min))
        return dt_arr

    def _populate_target_data(self, res_dct, tgt_dct, site, dt_arr,
                              keep_old=True):

        for key, target in tgt_dct.items():

            vis_dct = res_dct.get(key, None)
            if vis_dct is None:
                # no history for this target, so calculate values for full
                # time period
                cres = site.calc(target, dt_arr)
                vis_dct = cres.get_dict(columns=self._columns)
                vis_dct['time_utc'] = dt_arr
                res_dct[key] = vis_dct

            else:
                # we have some possible history for this target,
                # so only calculate values for the new time period
                # that we haven't already calculated
                t_arr = vis_dct['time_utc']
                if not keep_old:
                    # remove any old calculations not in this time period
                    mask = np.isin(t_arr, dt_arr, invert=True)
                    num_rem = mask.sum()
                    if num_rem > 0:
                        self.logger.debug(f"removing results for {num_rem} times")
                        for key in self._columns + ['time_utc']:
                            vis_dct[key] = vis_dct[key][~mask]

                # add any new calculations in this time period
                add_arr = np.setdiff1d(dt_arr, t_arr)
                num_add = len(add_arr)
                if num_add == 0:
                    self.logger.debug("no new calculations needed")
                elif num_add > 0:
                    self.logger.debug(f"adding results for {num_add} new times")
                    # only calculate for new times
                    cres = site.calc(target, add_arr)
                    dct = cres.get_dict(columns=self._columns)
                    dct['time_utc'] = add_arr

                    if len(vis_dct['time_utc']) == 0:
                        # we removed all the old data
                        vis_dct.update(dct)
                    else:
                        idxs = np.searchsorted(vis_dct['time_utc'], add_arr)
                        # insert new data
                        for key in self._columns + ['time_utc']:
                            vis_dct[key] = np.insert(vis_dct[key], idxs, dct[key])

    def populate_periods(self, tgt_dct, site, periods, keep_old=True):
        """Populate ephemeris for many targets over many periods.

        Parameters
        ----------
        tgt_dct : dict
            dict mapping keys to targets

        site : ~qplan.util.calcpos.Observer
            The site observing the targets

        periods : list of (start_time, stop_time)
            Where times are timezone-aware Python datetimes

        keep_old : bool (optional, defaults to True)
            Whether to keep old period data not specified in this range

        Returns
        -------
        None
        """
        # create one large date array of all periods
        start_time, stop_time = periods[0]
        dt_arr = self.get_date_array(start_time, stop_time)
        for start_time, stop_time in periods[1:]:
            dt_arr_n = self.get_date_array(start_time, stop_time)
            dt_arr = np.append(dt_arr, dt_arr_n, axis=0)

        self._populate_target_data(self.vis_catalog, tgt_dct, site, dt_arr,
                                   keep_old=keep_old)

    def get_closest(self, key, time_dt, precision_minutes=None):
        """Return the closest set of results for target to time

        Parameters
        ----------
        key : valid Python dict key
            The key that is used to store the results for a target

        time_dt : datetime.datetime
            Python timezone-aware datetime for the period we are interested in

        Returns
        -------
        res : dict of values
            A dict of values keyed by column name
        """
        vis_dct = self.get_target_data(key)
        if vis_dct is None:
            raise KeyError(f"No data for key {key} found")

        t_arr = vis_dct['time_utc']
        dt = time_dt.astimezone(tz.UTC).replace(tzinfo=None)
        idx = np.searchsorted(t_arr, dt, side='left')
        # Get values closest in time to dt
        if idx == len(t_arr):
            idx = idx - 1
        if idx > 0:
            t_lo, t_hi = t_arr[idx - 1].item(), t_arr[idx].item()
            if np.fabs((dt - t_lo).total_seconds()) < np.fabs((t_hi - dt).total_seconds()):
                idx = idx - 1
        res_dct = {key: vis_dct[key][idx]
                   for key in self._columns + ['time_utc']}
        # check closeness of dt to result
        t_res = res_dct['time_utc'].item()
        diff_sec = np.fabs((dt - t_res).total_seconds())

        if precision_minutes is None:
            precision_minutes = self.precision_minutes
        if diff_sec / 60.0 > precision_minutes:
            raise ValueError(f"time diff from result is {diff_sec:.2f} sec")
        return Bunch(res_dct)

    def observable_periods(self, tgt_dct, site, start_time, stop_time,
                           el_min_deg, el_max_deg, time_needed_sec,
                           period_check=None):
        """Check a target's visibility within a time period.

        Parameters
        ----------
        tgt_dct : dict
            dict mapping keys to targets

        site : ~qplan.util.calcpos.Observer
            The site observing the targets

        periods : list of (start_time, stop_time)
            Where times are timezone-aware Python datetimes

        keep_old : bool (optional, defaults to True)
            Whether to keep old period data not specified in this range

        Returns
        -------
        obs_dct : dict
            dict mapping keys to observability periods
        """
        if period_check is None:
            period_check = self.period_check

        if start_time.tzinfo is None or stop_time.tzinfo is None:
            raise ValueError("Please pass timezone-aware datetimes")
        tz_incoming = start_time.tzinfo

        if period_check:
            # ideally, this should be as efficient as possible if we have
            # already populated the time span
            self.populate_periods(tgt_dct, site,
                                  [(start_time, stop_time)],
                                  keep_old=True)

        _start_time = start_time.astimezone(tz.UTC).replace(tzinfo=None)
        _stop_time = stop_time.astimezone(tz.UTC).replace(tzinfo=None)

        obs_dct = dict()
        # TODO: can we parallelize this
        for key in tgt_dct:
            vis_dct = self.get_target_data(key)

            # Grab indices for times within our start and stop range
            utc_arr = vis_dct['time_utc']
            time_indices = np.where(np.logical_and(_start_time <= utc_arr,
                                                   utc_arr <= _stop_time))[0]
            utc_inrange = vis_dct['time_utc'][time_indices]

            # Limit altitude check to those indices
            alt_arr = vis_dct['alt_deg'][time_indices]

            # Now limit altitude check by min and max elevation limits
            alt_indices = np.where(np.logical_and(el_min_deg <= alt_arr,
                                                  alt_arr <= el_max_deg))[0]

            # check for, and separate, any gaps in the indices as separate
            # available visibility slices
            # (target may move above or below acceptable elevation, for example)
            vis_slices = split_array(alt_indices)

            # Report the times for the first available slice that can accomodate
            # the time_needed
            periods = []
            prec_sec = self.precision_minutes * 60.0
            for indices in vis_slices:
                utc_times = utc_inrange[indices]
                if len(utc_times) < 2:
                    continue
                time_rise = utc_times[0].item().replace(tzinfo=tz.UTC)
                time_set = utc_times[-1].item().replace(tzinfo=tz.UTC)

                diff = (time_set - time_rise).total_seconds()
                can_obs = (diff >= time_needed_sec)
                if can_obs:
                    if tz_incoming is not None:
                        time_rise = time_rise.astimezone(tz_incoming)
                        # if time_rise we have is close enough to the start_time
                        # passed in, pretend the time_rise is the passed in one
                        if np.fabs((time_rise - start_time).total_seconds()) <= prec_sec:
                            time_rise = start_time

                        time_set = time_set.astimezone(tz_incoming)
                        # ditto for time_set and stop_time
                        if np.fabs((time_set - stop_time).total_seconds()) <= prec_sec:
                            time_set = stop_time
                    periods.append((time_rise, time_set))

            obs_dct[key] = periods

        return obs_dct

    def observable(self, key, target, site, start_time, stop_time,
                   el_min_deg, el_max_deg, time_needed_sec,
                   period_check=None):
        """
        Return True if `target` is observable between `time_start` and
        `time_stop`, defined by whether it is between elevation `el_min`
        and `el_max` during that period, and whether it meets the minimum
        airmass.
        """
        obs_dct = self.observable_periods({key: target}, site,
                                          start_time, stop_time,
                                          el_min_deg, el_max_deg,
                                          time_needed_sec,
                                          period_check=period_check)
        periods = obs_dct[key]
        if len(periods) == 0:
            return (False, None, None)

        time_rise, time_set = periods[0]
        return (True, time_rise, time_set)


def split_array(arr):
    """Splits a NumPy array into subarrays based on index discontinuities.

    Parameters
    ----------
        arr: A 1D NumPy array.

    Returns
    -------
        A list of NumPy arrays representing the subarrays.
    """
    if len(arr) <= 1:
      return [arr]

    # find differences between i and i+1 indices
    diffs = np.diff(arr)
    # find split indices where the difference is > 1
    split_indices = np.array(np.where(diffs > 1)).flatten() + 1
    # split the array into sub-arrays along these indices
    sub_arrays = np.split(arr, split_indices)
    return sub_arrays


def _process_chunk(arg):
    global _mp_site, _mp_cache, _mp_tgts, _mp_dt_arr
    n, idxs = arg
    res_dct = dict()
    if len(idxs) == 0:
        return res_dct

    site = _mp_site.clone()

    tgt_dct = {i: _mp_tgts[i].clone() for i in idxs}
    dt_arr = _mp_dt_arr
    _mp_cache._populate_target_data(res_dct, tgt_dct, site, dt_arr,
                                    keep_old=True)
    return res_dct

def populate_periods_mp(eph_cache, targets, site, periods, keep_old=True):
    global _mp_site, _mp_cache, _mp_dt_arr, _mp_tgts
    _mp_site = site
    _mp_cache = eph_cache

    # create one large date array of all periods
    start_time, stop_time = periods[0]
    dt_arr = eph_cache.get_date_array(start_time, stop_time)
    for start_time, stop_time in periods[1:]:
        dt_arr_n = eph_cache.get_date_array(start_time, stop_time)
        dt_arr = np.append(dt_arr, dt_arr_n, axis=0)
    _mp_dt_arr = dt_arr

    #target_chunks = np.array_split(np.asarray(targets), core_count)
    # targets is often a set, need to index it
    targets = [tgt.clone() for tgt in targets]
    _mp_tgts = targets

    # associate indexes with targets
    arg_list = list(range(len(targets)))
    chunks = []
    for i in range(0, len(arg_list), core_count):
        chunks.append(arg_list[i:i + core_count])

    chunks = list(filter(lambda chunk: len(chunk) > 0, chunks))
    max_procs = min(core_count, len(chunks))
    arg_list = [(n, chunk) for n, chunk in enumerate(chunks)]

    with mp.Pool(processes=max_procs) as pool:
        res_lst = pool.map(_process_chunk, arg_list)
        for res_dct in res_lst:
            upd_dct = {targets[i]: vis_dct for i, vis_dct in res_dct.items()}
            eph_cache.vis_catalog.update(upd_dct)
