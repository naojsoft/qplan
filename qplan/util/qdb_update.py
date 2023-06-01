from pathlib import Path

from qplan import q_db

def connect_qdb(cfg_path, logger):

    if not Path(cfg_path).exists():
        raise ValueError(f"No queue database configuration in '{cfg_path}'")

    qdb = q_db.QueueDatabase(logger)

    # Set up Queue database access
    try:
        qdb.read_config(cfg_path)
        qdb.connect()
    except Exception as e:
        logger.error(f"Exception creating queue db client: {str(e)}", exc_info=True)
        raise e

    try:
        qa = q_db.QueueAdapter(qdb)
    except Exception as e:
        logger.error(f'Unexpected error while creating QueueAdapter: {str(e)}', exc_info=True)
        raise e

    return qa

def update_programs(qa, programsFile, logger):
    # store programs into db
    try:
        qt = qa.get_table('program')
    except Exception as e:
        logger.error(f'Unexpected error while connecting to program table in queue db: {str(e)}', exc_info=True)
        raise e

    try:
        for key, pgm in programsFile.programs_info.items():
            logger.info(f"adding record for program {key}")
            qt.put(pgm)
    except Exception as e:
        logger.error(f'Unexpected error while updating program table in queue db:  {str(e)}', exc_info=True)
        raise e

def update_ob(qa, inst_name, ob_qf_dict, logger):
    # store OBs into db
    try:
        qt = qa.get_table('ob')
    except Exception as e:
        logger.error(f'Unexpected error while connecting to ob table in queue db:  {str(e)}', exc_info=True)
        raise e

    try:
        for pgmName, pf in ob_qf_dict.items():
            if inst_name == 'PFS':
                obs_info = pf.obs_info
            elif inst_name == 'HSC':
                obs_info = pf.cfg['ob'].obs_info
            for ob in obs_info:
                logger.info(f"adding record for program {pgmName} OB {ob}")
                qt.put(ob)
    except Exception as e:
        logger.error(f'Unexpected error while updating ob table in queue db: {str(e)}', exc_info=True)
        raise e
