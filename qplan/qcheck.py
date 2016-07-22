#!/usr/bin/env python
#
# qcheck.py -- Queue file checker
#
# Russell Kackley (rkackley@naoj.org)
#
"""
Usage:
    qcheck.py -i <queue file directory>
    qcheck.py --file <Excel queue file>
"""

import sys, os
import logging
from ginga.misc import log

from qplan import filetypes
from qplan import entity

def main(options, args):
    # Create top level logger.
    logger = log.get_logger(name='qcheck', options=options)

    if options.input_filename:
        # This section is for reading an Excel file that has the usual
        # sheets in it (targets, envcfg, etc.)

        # Append any directory path supplied in options.input_filename
        # onto the end of the options.input_dir value.
        input_dir = os.path.join(options.input_dir, os.path.dirname(options.input_filename))
        # Parse the input filename so we can get the proposal name.
        input_filename = os.path.basename(options.input_filename)
        propname, ext = input_filename.split('.')
        if ext in filetypes.QueueFile.excel_ext:
            propdict = {}
            key = propname.upper()
            propdict[key] = entity.Program(key, hours=0, category='')
            progFile = filetypes.ProgramFile(input_dir, logger, propname, propdict)
        else:
            logger.error("File extension '%s' is not a valid file type. Must be one of %s." % (ext, filetypes.QueueFile.excel_ext))
            sys.exit(1)
    else:
        # This section is for reading a directory that contains CSV
        # files, i.e., targets.csv, inscfg.csv, etc.
        dirname = os.path.dirname(options.input_dir)
        propname = os.path.basename(options.input_dir)
        propdict = {}
        key = propname.upper()
        propdict[key] = entity.Program(key, hours=0, category='')
        progFile = filetypes.ProgramFile(dirname, logger, propname, propdict, file_ext='csv')

    logger.info('Warning count is %d' % progFile.warn_count)
    logger.info('Error count is   %d' % progFile.error_count)

if __name__ == "__main__":

    # Parse command line options with nifty new optparse module
    from optparse import OptionParser

    usage = "usage: %prog [options] cmd [args]"
    optprs = OptionParser(usage=usage, version=('%%prog'))

    optprs.add_option("--debug", dest="debug", default=False, action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("-i", "--input", dest="input_dir", default=".",
                      metavar="DIRECTORY",
                      help="Read input files from DIRECTORY")
    optprs.add_option("--file", dest="input_filename", default=None,
                      metavar="INPUT_FILENAME",
                      help="Input filename")
    optprs.add_option("--log", dest="logfile", metavar="FILE",
                      help="Write logging output to FILE")
    optprs.add_option("--loglevel", dest="loglevel", metavar="LEVEL",
                      type='int', default=logging.INFO,
                      help="Set logging level to LEVEL")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    optprs.add_option("--stderr", dest="logstderr", default=False,
                      action="store_true",
                      help="Copy logging also to stderr")

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
