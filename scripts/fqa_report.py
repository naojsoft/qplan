#! /usr/bin/env python3
"""
Prepare FQA reports for Queue working group

Usage:
    $ fqa_report.py --fqa-staff=Fujiyoshi YYYY-MM-DD
"""
import sys, os
from argparse import ArgumentParser

from dateutil import parser, tz
from datetime import timedelta, datetime

from qplan import q_db, q_query, entity

from ginga.misc.log import get_logger

def split_obs_by_proposal(ex_obs):
    dct = dict()
    for ex_ob in ex_obs:
        ob_key = ex_ob.ob_key
        prop_id, ob_code = ob_key
        lst = dct.setdefault(prop_id, [])
        lst.append(ob_code)
    return dct

def main(options, args):

    if len(args) != 1:
        print("Please specify a date (YYYY-MM-DD) for an observation night in HST")
        sys.exit(1)

    if options.fqa_staff is None:
        print("Please specify a FQA staff name with --fqa-staff")
        sys.exit(1)

    logger = get_logger(name="fqa_report", level=20, log_stderr=False)

    tz_HST = tz.gettz("HST")
    dt = parser.parse(args[0])
    from_dt = dt.replace(hour=17, minute=0, tzinfo=tz_HST)
    to_dt = from_dt + timedelta(hours=14)

    fqa_date = options.fqa_date
    if fqa_date is None:
        fqa_dt = datetime.now(tz=tz_HST)
    else:
        fqa_dt = parser.parse(fqa_date)
        fqa_dt = dt.replace(tzinfo=tz_HST)
    fqa_dt_ut = dt.astimezone(tz.UTC)

    qdb = q_db.QueueDatabase(logger)

    if options.cfgfile is not None:
        cfg_file = options.cfgfile
    else:
        conf_home = os.environ.get('CONFHOME', None)
        if conf_home is not None:
            cfg_file = os.path.join(conf_home, 'qplan', 'qdb_rd.yml')
        else:
            cfg_file = os.path.join(os.path.expanduser('~'), '.qplan',
                                    'qdb.yml')

    qdb.read_config(cfg_file)
    qdb.connect()
    qa = q_db.QueueAdapter(qdb)
    qq = q_query.QueueQuery(qa, use_cache=False)

    ex_obs = list(qq.get_executed_obs_by_date(from_dt, to_dt))

    obs_dt_ut = from_dt.astimezone(tz.UTC)

    if options.outfile is None:
        outfile = sys.stdout
    else:
        outfile = open(options.outfile, "w")

    print("Observation Date (UT): {}".format(obs_dt_ut.strftime("%Y-%m-%d")),
          file=outfile)
    print("FQA Date (UT): {}".format(fqa_dt_ut.strftime("%Y-%m-%d")),
          file=outfile)
    print("FQA Staff: {}".format(options.fqa_staff),
          file=outfile)
    print("", file=outfile)
    print("Total number of executed OBs is {}".format(len(ex_obs)),
          file=outfile)
    print("", file=outfile)
    good_obs = list(filter(lambda ex_ob: ex_ob.fqa == "good", ex_obs))
    good_obs.sort(key=lambda ex_ob: ex_ob.time_start)
    bad_obs = list(filter(lambda ex_ob: ex_ob.fqa == "bad", ex_obs))
    bad_obs.sort(key=lambda ex_ob: ex_ob.time_start)

    print("Total number of good executed OBs is {}".format(len(good_obs)),
          file=outfile)
    print("", file=outfile)
    dct = split_obs_by_proposal(good_obs)
    prop_ids = list(dct.keys())
    prop_ids.sort()
    for prop_id in prop_ids:
        print("{}: {}".format(prop_id, ", ".join(dct[prop_id])),
              file=outfile)
        print("", file=outfile)

    print("Total number of bad executed OBs is {}".format(len(bad_obs)),
          file=outfile)
    print("", file=outfile)
    dct = split_obs_by_proposal(bad_obs)
    prop_ids = list(dct.keys())
    prop_ids.sort()
    for prop_id in prop_ids:
        print("{}: {}".format(prop_id, ", ".join(dct[prop_id])),
              file=outfile)
        print("", file=outfile)


if __name__ == "__main__":

    argprs = ArgumentParser(description="Create FQA report for HSC")
    argprs.add_argument("--cfgfile", dest="cfgfile", default=None,
                        metavar="FILE",
                        help="Configuration file for accessing QueueDB")
    argprs.add_argument("--fqa-date", dest="fqa_date", default=None,
                        metavar="YYYY-MM-DD",
                        help="Date the Final Quality Assessment was done (defaults to now)")
    argprs.add_argument("--fqa-staff", dest="fqa_staff", default=None,
                        metavar="NAME",
                        help="Name of the staff doing FQA")
    argprs.add_argument("-o", "--outfile", dest="outfile", default=None,
                        metavar="FILE",
                        help="Write report to FILE")

    (options, args) = argprs.parse_known_args(sys.argv[1:])

    main(options, args)
