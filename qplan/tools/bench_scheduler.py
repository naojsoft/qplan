#!/usr/bin/env python3
#
# bench_scheduler.py -- headless benchmark / profiler for the queue scheduler.
#
# Loads a phase-2 data directory (the same files the ControlPanel "Load Info"
# button reads), enables a chosen number of nights (equivalent to clearing the
# "skip" column in schedule.xlsx), runs Scheduler.schedule_all() -- the work
# "Build Schedule" kicks off -- under cProfile, and prints a baseline of the
# metrics we care about (wall time, %/count scheduled, unique targets) plus the
# hottest functions.
#
# Example:
#   python -m qplan.tools.bench_scheduler ~/tmp/qplan_testdata --nights 1
#
import sys
import time
import cProfile
import pstats
import io
import logging
from argparse import ArgumentParser

from ginga.misc.log import get_logger
from ginga.misc import Bunch

from qplan import filetypes
from qplan.Scheduler import Scheduler
from qplan.util import site as qsite


def load_dataset(input_dir, logger, file_ext='xlsx'):
    """Replicate ControlPanel.initialize_model + update_scheduler (headless).

    Returns a Bunch with weights, schedule_info, programs_info and the
    assembled scheduler OB list.
    """
    weights = filetypes.WeightsFile(input_dir, logger, file_ext=file_ext)
    schedule = filetypes.ScheduleFile(input_dir, logger, file_ext=file_ext)
    programs = filetypes.ProgramsFile(input_dir, logger, file_ext=file_ext)
    pi = programs.programs_info

    # load OBs for every non-skipped program (HSC path).  Mirror
    # ControlPanel.load_program: skip (don't abort) any program that fails
    # to load, so a single bad proposal file doesn't sink the whole run.
    ob_dict = {}
    ob_keys = []
    n_progs = 0
    for propname, prog in pi.items():
        if prog.skip:
            continue
        if 'HSC' not in prog.instruments:
            logger.warning("skipping non-HSC program %s (%s)" % (
                propname, prog.instruments))
            continue
        try:
            pf = filetypes.ProgramFile(input_dir, logger, propname, pi,
                                       file_ext=file_ext)
            obs_info = pf.cfg['ob'].obs_info
        except Exception as e:
            logger.warning("skipping program %s (load failed: %s)" % (
                propname, e))
            continue
        n_progs += 1
        for ob in obs_info:
            key = (propname, ob.name)
            ob_dict[key] = ob
            ob_keys.append(key)

    ob_keys.sort()
    oblist = [ob_dict[key] for key in ob_keys]

    return Bunch.Bunch(weights=weights.weights,
                       schedule_info=schedule.schedule_info,
                       programs_info=pi, oblist=oblist, n_progs=n_progs)


def configure_scheduler(logger, data, num_nights):
    """Build and configure a Scheduler; enable the first `num_nights` nights."""
    observer = qsite.get_site('subaru')
    sdlr = Scheduler(logger, observer)

    # enable the first `num_nights` schedule records (== clearing "skip")
    enabled = 0
    for rec in data.schedule_info:
        if enabled >= num_nights:
            rec.skip = True
        else:
            rec.skip = False
            enabled += 1

    sdlr.set_weights(data.weights)
    sdlr.set_schedule_info(data.schedule_info)
    sdlr.set_programs_info(data.programs_info)
    sdlr.set_scheduling_params(dict(limit_filter=None, allow_delay=True))
    sdlr.set_apriori_program_info({})
    sdlr.set_oblist_info(data.oblist)
    return sdlr, enabled


def summarize(sdlr):
    """Return scheduling result metrics as a Bunch."""
    n_scheduled = 0
    targets = set()
    for schedule in sdlr.schedules:
        for slot in schedule.slots:
            ob = slot.ob
            if ob is not None and not ob.derived:
                n_scheduled += 1
                targets.add((ob.target.ra, ob.target.dec))
    n_obs = len(sdlr.oblist)
    return Bunch.Bunch(n_obs=n_obs, n_nights=len(sdlr.schedules),
                       n_scheduled=n_scheduled, n_targets=len(targets),
                       pct=(100.0 * n_scheduled / n_obs) if n_obs else 0.0)


def main(args):
    logger = get_logger('bench', level=args.loglevel, log_stderr=True)

    t0 = time.time()
    data = load_dataset(args.input_dir, logger, file_ext=args.file_ext)
    t_load = time.time() - t0
    print("loaded %d OBs from %d programs in %.2f sec" % (
        len(data.oblist), data.n_progs, t_load))

    sdlr, enabled = configure_scheduler(logger, data, args.nights)
    print("scheduling %d night(s), %d OBs..." % (enabled, len(data.oblist)))

    prof = cProfile.Profile()
    t0 = time.time()
    prof.enable()
    sdlr.schedule_all()
    prof.disable()
    wall = time.time() - t0

    res = summarize(sdlr)
    print("\n==================== BASELINE ====================")
    print("wall time (schedule_all): %8.3f sec" % (wall,))
    print("nights scheduled        : %8d" % (res.n_nights,))
    print("OBs available           : %8d" % (res.n_obs,))
    print("OBs scheduled           : %8d  (%.1f%%)" % (res.n_scheduled, res.pct))
    print("unique targets          : %8d" % (res.n_targets,))
    print("==================================================\n")

    for sort_key in ('tottime', 'cumtime'):
        s = io.StringIO()
        ps = pstats.Stats(prof, stream=s).sort_stats(sort_key)
        ps.print_stats(args.top)
        print("---- top %d by %s ----" % (args.top, sort_key))
        # keep only the ranked lines (skip the pstats preamble)
        for line in s.getvalue().splitlines():
            if 'function calls' in line or line.strip().startswith('ncalls'):
                print(line)
            elif line.strip() and line.lstrip()[0].isdigit():
                print(line)
        print()

    if args.dump is not None:
        prof.dump_stats(args.dump)
        print("wrote raw profile to %s (view with snakeviz/pstats)" % args.dump)


if __name__ == '__main__':
    ap = ArgumentParser(description="Headless queue-scheduler benchmark/profiler")
    ap.add_argument("input_dir", help="phase-2 data directory (weights/schedule/"
                    "programs .xlsx + per-program .xlsx)")
    ap.add_argument("--nights", type=int, default=1,
                    help="number of nights to enable for scheduling (default: 1)")
    ap.add_argument("--file-ext", default='xlsx', help="input file format")
    ap.add_argument("--top", type=int, default=25,
                    help="number of hottest functions to show")
    ap.add_argument("--dump", default=None,
                    help="write raw cProfile stats to this path")
    ap.add_argument("--loglevel", type=int, default=logging.ERROR,
                    help="logging level (default: ERROR=40)")
    main(ap.parse_args(sys.argv[1:]))
