#!/usr/bin/env python
#
# qcheck.py -- Queue file checker
#
# R. Kackley
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

    from argparse import ArgumentParser
    argprs = ArgumentParser(description="Queue Phase 2 file checker")

    argprs.add_argument("-i", "--input", dest="input_dir", default=".",
                        metavar="DIRECTORY",
                        help="Read input files from DIRECTORY")
    argprs.add_argument("--file", dest="input_filename", default=None,
                        metavar="INPUT_FILENAME",
                        help="Input filename")
    argprs.add_argument("--log", dest="logfile", metavar="FILE",
                        help="Write logging output to FILE")
    argprs.add_argument("--loglevel", dest="loglevel", metavar="LEVEL",
                        type=int, default=logging.INFO,
                        help="Set logging level to LEVEL")
    argprs.add_argument("--stderr", dest="logstderr", default=False,
                        action="store_true",
                        help="Copy logging also to stderr")

    (options, args) = argprs.parse_known_args(sys.argv[1:])

    main(options, args)
