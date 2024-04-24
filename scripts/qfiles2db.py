#!/usr/bin/env python

import argparse
import os
from pathlib import Path
import sys

from ginga.misc import log
from qplan import filetypes
from qplan.util import qdb_update

def main(options, args):
    logger = log.get_logger('pfs_qfiles', options=options)
    logger.info(f'input_dir {options.input_dir}')

    if options.inst_name == 'PFS':
        input_fmt = 'csv'
    elif options.inst_name == 'HSC':
        input_fmt = 'xlsx'

    programsFile = filetypes.ProgramsFile(options.input_dir, logger, file_ext=input_fmt)
    logger.info(f'programsFile.programs_info {programsFile.programs_info}')

    ob_qf_dict = {}

    for pgmName, pgm in programsFile.programs_info.items():
        logger.info(f'pgmName {pgmName} pgm.proposal {pgm.proposal} pgm.grade {pgm.grade} pgm.rank {pgm.rank} pgm.total_time {pgm.total_time} {pgm.instruments}')
        if options.inst_name == 'PFS':
            pf = filetypes.PFS_ProgramFile(options.input_dir, logger, pgm.proposal, programsFile.programs_info, file_ext=input_fmt)
            logger.info(f'pgmName {pgmName} pf {pf}')
        elif options.inst_name == 'HSC':
            pf = filetypes.ProgramFile(options.input_dir, logger, pgm.proposal, programsFile.programs_info, file_ext=input_fmt)
        ob_qf_dict[pgmName] = pf

    if options.dry_run:
        logger.info(f'dry run - not updating database')
    else:
        config_filepath = Path(options.config_file)
        if not config_filepath.exists():
            config_dir = 'qplan'
            if ('CONFHOME' in os.environ and
                len(os.environ['CONFHOME'].strip()) > 0):
                config_filepath = Path(os.environ['CONFHOME']) / config_dir / options.config_file
            else:
                config_filepath = Path(os.environ['HOME']) / config_dir / options.config_file

        try:
            logger.info(f'Create queue database client using {config_filepath}')
            qa = qdb_update.connect_qdb(config_filepath, logger)
        except Exception as e:
            logger.error(f"Exception creating queue db client: {e}", exc_info=True)
            sys.exit(1)

        # store programs into db
        qdb_update.update_programs(qa, programsFile, logger)

        # store OBs into db
        qdb_update.update_ob(qa, options.inst_name, ob_qf_dict, logger)

        logger.info("done updating database")

if __name__ == "__main__":

    argprs = argparse.ArgumentParser(description='Read Phase 2 queue files and update queue database')

    argprs.add_argument("--inst", dest="inst_name", default="PFS", choices=['HSC', 'PFS'],
                        metavar="INSTRUMENT NAME",
                        help="Instrument name (HSC or PFS)")
    argprs.add_argument("-i", "--input", dest="input_dir", default=".",
                        metavar="DIRECTORY",
                        help="Read input files from DIRECTORY")
    argprs.add_argument("-n", "--dry-run", dest="dry_run", action='store_true',
                        help="Dry run - don't write to database")
    argprs.add_argument("-f", "--config", dest="config_file", default='qdb.yml',
                        help="YAML configuration file")

    log.addlogopts(argprs)

    (options, args) = argprs.parse_known_args(sys.argv[1:])

    main(options, args)

#END
