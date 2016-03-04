from __future__ import print_function
import os, sys
import logging
import StringIO

from ginga.misc import log
from ginga.misc.Bunch import Bunch

import transaction

from qplan import filetypes, Model, Scheduler, q_db

class StandAlone_Scheduler(object):

    def __init__(self, logger, input_dir, host, port):
        self.logger = logger
        self.input_dir = input_dir
        self.input_fmt = 'xls'
        self.schedules = []

        self.model = Model.QueueModel(self.logger)
        self.sdlr = self.model.get_scheduler()
        self.sdlr.add_callback('schedule-completed', self.sdl_completed_cb)

        self.addr = (host, port)


    def initialize_model(self):
        try:
            # read weights
            self.logger.info("reading weights from %s" % (self.input_dir))
            self.weights_qf = filetypes.WeightsFile(self.input_dir, self.logger,
                                                    file_ext='xlsx')
            self.model.set_weights_qf(self.weights_qf)

            # read schedule
            self.logger.info("reading schedule from %s" % (self.input_dir))
            self.schedule_qf = filetypes.ScheduleFile(self.input_dir,
                                                      self.logger,
                                                      file_ext='xlsx')
            self.model.set_schedule_qf(self.schedule_qf)

            # read proposals
            self.logger.info("reading proposals from %s" % (self.input_dir))
            self.programs_qf = filetypes.ProgramsFile(self.input_dir,
                                                      self.logger,
                                                    file_ext='xlsx')
            self.model.set_programs_qf(self.programs_qf)

            # read observing blocks
            self.ob_qf_dict = {}
            self.tgtcfg_qf_dict = {}
            self.envcfg_qf_dict = {}
            self.inscfg_qf_dict = {}
            self.telcfg_qf_dict = {}
            self.oblist_info = []

            propnames = list(self.programs_qf.programs_info.keys())
            propnames.sort()

            for propname in propnames:
                pf = filetypes.ProgramFile(self.input_dir, self.logger,
                                           propname,
                                           self.programs_qf.programs_info,
                                           file_ext=self.input_fmt)

                # Set telcfg
                telcfg_qf = pf.cfg['telcfg']
                self.telcfg_qf_dict[propname] = telcfg_qf
                self.model.set_telcfg_qf_dict(self.telcfg_qf_dict)

                # Set inscfg
                inscfg_qf = pf.cfg['inscfg']
                self.inscfg_qf_dict[propname] = inscfg_qf
                self.model.set_inscfg_qf_dict(self.inscfg_qf_dict)

                # Set envcfg
                envcfg_qf = pf.cfg['envcfg']
                self.envcfg_qf_dict[propname] = envcfg_qf
                self.model.set_envcfg_qf_dict(self.envcfg_qf_dict)

                # Set targets
                tgtcfg_qf = pf.cfg['targets']
                self.tgtcfg_qf_dict[propname] = tgtcfg_qf
                self.model.set_tgtcfg_qf_dict(self.tgtcfg_qf_dict)

                # Finally, set OBs
                self.ob_qf_dict[propname] = pf.cfg['ob']
                #self.oblist_info.extend(self.oblist[propname].obs_info)
                self.model.set_ob_qf_dict(self.ob_qf_dict)

        except Exception as e:
            self.logger.error("Error initializing: %s" % (str(e)))

    def update_scheduler(self):
        sdlr = self.model.get_scheduler()
        try:
            sdlr.set_weights(self.weights_qf.weights)
            sdlr.set_schedule_info(self.schedule_qf.schedule_info)
            sdlr.set_programs_info(self.programs_qf.programs_info)

            # TODO: this maybe should be done in the Model
            self.oblist_info = []
            propnames = list(self.programs_qf.programs_info.keys())
            propnames.sort()
            #for propname in self.programs_qf.programs_info:
            for propname in propnames:
                self.oblist_info.extend(self.ob_qf_dict[propname].obs_info)
            sdlr.set_oblist_info(self.oblist_info)

        except Exception as e:
            self.logger.error("Error storing into scheduler: %s" % (str(e)))

        self.logger.info("scheduler initialized")

    def sdl_completed_cb(self, sdlr, completed, uncompleted, schedules):
        self.schedules = schedules

    def schedule_files(self):
        self.initialize_model()
        self.update_scheduler()

        self.model.schedule_all()


    def init_db(self):
        self.initialize_model()
        self.update_scheduler()

        # open the queue database
        db = q_db.QueueDatabase(self.logger, self.addr)
        qa = q_db.QueueAdapter(db)

        sdlr = self.model.get_scheduler()

        # store programs into db
        programs = qa.get_table('program')
        for key in sdlr.programs:
            programs[key] = sdlr.programs[key]

        # store OBs into db
        ob_db = qa.get_table('ob')
        for ob in sdlr.oblist:
            key = (ob.program.proposal, ob.name)
            print("adding record for OB '%s'" % (str(key)))
            ob_db[key] = ob

        transaction.commit()

        qa.close()


    def schedule_db(self):
        weights = Bunch(dict(w_delay=5.0, w_filterchange=0.3, w_slew=0.2,
                             w_rank=0.3, w_priority=0.1))

        # data should be shared by all schedule elements, I believe
        data = Bunch(dict(seeing=0.5, transparency=0.9,
                          filters=['g', 'r', 'i', 'z', 'y', 'sh'],
                          instruments=['HSC'], dome='open', categories=['open']))
        schedule = [Bunch(dict(date='2016-03-07', starttime='19:42:00',
                               stoptime='05:23:00', data=data, note='')),
                    ]

        # open the queue database
        db = q_db.QueueDatabase(self.logger, self.addr)
        qa = q_db.QueueAdapter(db)

        sdlr = self.model.get_scheduler()

        # these two read not from db
        sdlr.set_weights(weights)
        sdlr.set_schedule_info(schedule)

        programs = qa.get_table('program')
        sdlr.set_programs_info(programs)

        ob_tbl = qa.get_table('ob')
        oblist = ob_tbl.values()
        sdlr.set_oblist_info(oblist)

        sdlr.schedule_all()



def main(options, args):
    # Create top level logger.
    logger = log.get_logger(name='t_schedule', options=options)

    sdl = StandAlone_Scheduler(logger, options.input_dir,
                               options.host, options.port)

    sdl.init_db()
    #sdl.schedule_files()
    #sdl.schedule_db()

    sys.exit(0)


if __name__ == "__main__":

    # Parse command line options with nifty new optparse module
    from optparse import OptionParser

    usage = "usage: %prog [options]"
    optprs = OptionParser(usage=usage)

    optprs.add_option("--debug", dest="debug", default=False, action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("--host", dest="host", default="localhost",
                      metavar="HOST",
                      help="Connect to HOST for db server")
    optprs.add_option("-i", "--input", dest="input_dir", default=".",
                      metavar="DIRECTORY",
                      help="Read input files from DIRECTORY")
    optprs.add_option("--log", dest="logfile", metavar="FILE",
                      help="Write logging output to FILE")
    optprs.add_option("--loglevel", dest="loglevel", metavar="LEVEL",
                      type='int', default=logging.INFO,
                      help="Set logging level to LEVEL")
    optprs.add_option("-o", "--output", dest="output_dir", default="output",
                      metavar="DIRECTORY",
                      help="Write output files to DIRECTORY")
    optprs.add_option("--port", dest="port", metavar="PORT",
                      type='int', default=9800,
                      help="Connect to PORT at server host")
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
