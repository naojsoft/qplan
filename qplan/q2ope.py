#!/usr/bin/env python
#
# q2ope.py -- Queue integration with legacy OPE
#
# Eric Jeschke (eric@naoj.org)
#
"""
Usage:
    q2ope.py
"""
from __future__ import print_function
# stdlib imports
import sys, os
from io import BytesIO, StringIO

# 3rd party imports
from ginga.misc import log
from ginga.util import six

# Local imports
from . import entity
from .Model import QueueModel


version = '20150105.0'


class QueueLoader(object):

    def __init__(self, model, logger, options):
        self.model = model
        self.logger = logger
        self.input_dir = options.input_dir.strip()

        self.schedule_qf = None
        self.programs_qf = None
        self.ob_qf_dict = None
        self.oblist_info = []

    def initialize_model(self):
        try:
            # read schedule
            schedule_file = os.path.join(self.input_dir, "schedule.csv")
            if not os.path.exists(schedule_file):
                self.logger.error("File not readable: %s" % (schedule_file))
                return
            self.logger.info("reading schedule from %s" % (schedule_file))
            self.schedule_qf = entity.ScheduleFile(schedule_file, self.logger)
            self.model.set_schedule_qf(self.schedule_qf)

            # read proposals
            proposal_file = os.path.join(self.input_dir, "programs.csv")
            if not os.path.exists(proposal_file):
                self.logger.error("File not readable: %s" % (proposal_file))
                return
            self.logger.info("reading proposals from %s" % (proposal_file))
            self.programs_qf = entity.ProgramsFile(proposal_file, self.logger)
            self.model.set_programs_qf(self.programs_qf)

            # read observing blocks
            self.ob_qf_dict = {}
            self.oblist_info = []

            propnames = list(self.programs_qf.programs_info.keys())
            propnames.sort()

            for propname in propnames:
                obfile = os.path.join(self.input_dir, propname+".csv")
                if not os.path.exists(obfile):
                    self.logger.error("File not readable: %s" % (obfile))
                    continue
                self.logger.info("loading observing blocks from file %s" % obfile)
                self.ob_qf_dict[propname] = entity.OBListFile(obfile, self.logger,
                                                          propname,
                                                          self.programs_qf.programs_info)
            self.model.set_ob_qf_dict(self.ob_qf_dict)

        except Exception as e:
            self.logger.error("Error initializing: %s" % (str(e)))


    def update_model(self):
        try:
            self.model.set_schedule_info(self.schedule_qf.schedule_info)
            self.model.set_programs_info(self.programs_qf.programs_info)

            # TODO: this maybe should be done in the Model
            self.oblist_info = []
            propnames = list(self.programs_qf.programs_info.keys())
            propnames.sort()
            #for propname in self.programs_qf.programs_info:
            for propname in propnames:
                self.oblist_info.extend(self.ob_qf_dict[propname].obs_info)
            # TODO: only needed if we ADD or REMOVE programs
            self.model.set_oblist_info(self.oblist_info)

        except Exception as e:
            self.logger.error("Error storing into model: %s" % (str(e)))

        self.logger.info("model initialized")

class BaseConverter(object):

    def __init__(self, logger):
        self.logger = logger

    def _mk_out(self, out_f):
        def out(*args):
            print(*args, file=out_f)
        return out

    def ra_to_funky(self, ra):
        return float(ra.replace(':', ''))

    def dec_to_funky(self, dec):
        return float(dec.replace(':', ''))


def main(options, args):

    # Create top level logger.
    logger = log.make_logger('ob2ope', options=options)

    # create queue model, loader and OPE converter
    model = QueueModel(logger=logger)
    loader = QueueLoader(model, logger, options)
    converter = SPCAM.Converter(logger)

    # load the data
    loader.initialize_model()
    loader.update_model()

    # buffer for OPE output
    if six.PY2:
        out_f = BytesIO()
    else:
        out_f = StringIO()

    # write preamble
    converter.write_ope_header(out_f)

    # convert each OB
    oblist = loader.oblist_info
    for ob in oblist:
        converter.ob_to_ope(ob, out_f)

    # here's the OPE file
    print(out_f.getvalue())


if __name__ == "__main__":

    # Parse command line options with nifty new optparse module
    from optparse import OptionParser

    usage = "usage: %prog [options] cmd [args]"
    optprs = OptionParser(usage=usage, version=('%%prog %s' % version))

    optprs.add_option("--debug", dest="debug", default=False, action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("-i", "--input", dest="input_dir", default="input",
                      metavar="DIRECTORY",
                      help="Read input files from DIRECTORY")
    optprs.add_option("-o", "--output", dest="output_dir", default="output",
                      metavar="DIRECTORY",
                      help="Write output files to DIRECTORY")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    log.addlogopts(optprs)

    (options, args) = optprs.parse_args(sys.argv[1:])

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print("%s profile:" % sys.argv[0])
        profile.run('main(options, args)')


    else:
        main(options, args)

# END
