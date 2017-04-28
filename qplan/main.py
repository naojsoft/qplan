#
# main.py -- Queue planner/scheduler main program logic
#

#
# stdlib imports
import sys, os
import threading
import logging

# Subaru python stdlib imports
from ginga.misc import ModuleManager, Settings, Task
from ginga.misc.Bunch import Bunch
from ginga.misc import log
import ginga.toolkit as ginga_toolkit

# Local application imports
from .Control import Controller
from .Model import QueueModel
from .Scheduler import Scheduler
from . import version
from .util import site

moduleHome = os.path.split(sys.modules['qplan.version'].__file__)[0]
sys.path.insert(0, moduleHome)
pluginHome = os.path.join(moduleHome, 'plugins')
sys.path.insert(0, pluginHome)

default_layout = ['seq', {},
                   ['vbox', dict(name='top', width=1440, height=900),
                    dict(row=['hbox', dict(name='menu')],
                         stretch=0),
                    dict(row=['hpanel', {},
                     ['ws', dict(name='left', width=100, show_tabs=False),
                      # (tabname, layout), ...
                      ],
                     ['vpanel', dict(width=700),
                      ['hpanel', dict(height=400),
                       ['vbox', dict(name='main', width=700),
                        dict(row=['ws', dict(name='report', group=1)], stretch=1)],
                       ['ws', dict(name='right', width=350, group=2),
                        # (tabname, layout), ...
                        ],
                       ],
                      ['hpanel', {},
                       ['ws', dict(name='sub1', width=700, height=520,
                                   group=1)],
                       ['ws', dict(name='sub2', width=500, group=1)],
                       ],
                      ],
                     ], stretch=1),
                    dict(row=['hbox', dict(name='status')], stretch=0),
                    ]]


plugins = [
    Bunch(name='slewchart', module='SlewChart', klass='SlewChart',
          tab='Slew Chart', ws='sub2', start=True),
    Bunch(name='airmasschart', module='AirMassChart', klass='AirMassChart',
          tab='Airmass Chart', ws='sub1', start=True),
    Bunch(name='schedule', module='Schedule', klass='Schedule',
          tab='Schedule', ws='left', start=True),
    Bunch(name='report', module='Report', klass='Report',
          tab='Report', ws='report', start=True),
    Bunch(name='logger', module='Logger', klass='Logger',
          tab='Log', ws='report', start=True),
    Bunch(name='cp', module='ControlPanel', klass='ControlPanel',
          tab='Control Panel', ws='right', start=True),
    Bunch(name='night_activity', module='SumChart', klass='NightSumChart',
          tab='Night Activity Chart', ws='sub1', start=True),
    Bunch(name='night_sched', module='SumChart', klass='SchedSumChart',
          tab='Schedules Chart', ws='sub1', start=True),
    Bunch(name='proposals', module='SumChart', klass='ProposalSumChart',
          tab='Proposals Chart', ws='sub1', start=True),
    Bunch(name='semester', module='SumChart', klass='SemesterSumChart',
          tab='Semester Chart', ws='sub1', start=True),
    Bunch(name='errors', module='Errors', klass='Errors',
          tab='Errors', ws='right', start=True),
    ]


class QueuePlanner(object):
    """
    This class exists solely to be able to customize the queue planner
    startup/application.
    """
    def __init__(self, layout=default_layout):
        self.plugins = []
        self.layout = layout

    def add_plugins(self, plugins):
        self.plugins.extend(plugins)

    def add_default_options(self, optprs):
        """
        Adds the default reference viewer startup options to an
        OptionParser instance `optprs`.
        """
        optprs.add_option("-c", "--completed", dest="completed", default=None,
                          metavar="FILE",
                          help="Specify FILE of completed OB keys")
        optprs.add_option("--date-start", dest="date_start", default=None,
                          help="Define the start of the schedule ('YYYY-MM-DD HH:MM')")
        optprs.add_option("--date-stop", dest="date_stop", default=None,
                          help="Define the end of the schedule ('YYYY-MM-DD HH:MM')")
        optprs.add_option("--debug", dest="debug", default=False, action="store_true",
                          help="Enter the pdb debugger on main()")
        optprs.add_option("--display", dest="display", metavar="HOST:N",
                          help="Use X display on HOST:N")
        optprs.add_option("-g", "--geometry", dest="geometry",
                          metavar="GEOM", default=None,
                          help="X geometry for initial size and placement")
        optprs.add_option("-i", "--input", dest="input_dir", default=".",
                          metavar="DIRECTORY",
                          help="Read input files from DIRECTORY")
        optprs.add_option("-f", "--format", dest="input_fmt", default=None,
                          metavar="FILE_FORMAT",
                          help="Specify input file format (csv, xls, or xlsx)")
        ## optprs.add_option("--modules", dest="modules", metavar="NAMES",
        ##                   help="Specify additional modules to load")
        optprs.add_option("--numthreads", dest="numthreads", type="int",
                          default=30,
                          help="Start NUM threads in thread pool", metavar="NUM")
        optprs.add_option("-o", "--output", dest="output_dir", default=None,
                          metavar="DIRECTORY",
                          help="Write output files to DIRECTORY")
        optprs.add_option("--profile", dest="profile", action="store_true",
                          default=False,
                          help="Run the profiler on main()")
        optprs.add_option("-s", "--site", dest="sitename", metavar="NAME",
                          default='subaru',
                          help="Observing site NAME")
        optprs.add_option("-t", "--toolkit", dest="toolkit", metavar="NAME",
                          default=None,
                          help="Prefer GUI toolkit (default: choose one)")
        log.addlogopts(optprs)


    def main(self, options, args):
        # Create top level logger.
        svcname = 'qplan'
        logger = log.get_logger(name=svcname, options=options)

        logger.info("starting qplan %s" % (version.version))

        ev_quit = threading.Event()

        thread_pool = Task.ThreadPool(logger=logger, ev_quit=ev_quit,
                                     numthreads=options.numthreads)

        if options.toolkit is not None:
            ginga_toolkit.use(options.toolkit)
        else:
            ginga_toolkit.choose()

        tkname = ginga_toolkit.get_family()
        logger.info("Chosen toolkit (%s) family is '%s'" % (
            ginga_toolkit.toolkit, tkname))

        from qplan.View import Viewer
        # must import AFTER Viewer
        from ginga.rv.Control import GuiLogHandler

        class QueuePlanner(Controller, Viewer):

            def __init__(self, logger, thread_pool, module_manager, preferences,
                         ev_quit, model):

                Viewer.__init__(self, logger, ev_quit)
                Controller.__init__(self, logger, thread_pool, module_manager,
                                    preferences, ev_quit, model)

        # Get settings folder
        ## if os.environ.has_key('CONFHOME'):
        ##     basedir = os.path.join(os.environ['CONFHOME'], svcname)
        ## else:
        basedir = os.path.join(os.environ['HOME'], '.' + svcname)
        if not os.path.exists(basedir):
            os.mkdir(basedir)
        prefs = Settings.Preferences(basefolder=basedir, logger=logger)

        settings = prefs.create_category('general')
        settings.load(onError='silent')
        settings.set_defaults(output_dir=options.output_dir)

        mm = ModuleManager.ModuleManager(logger)

        ## # Add any custom modules
        ## if options.modules:
        ##     modules = options.modules.split(',')
        ##     for mdlname in modules:
        ##         #self.mm.loadModule(name, pfx=pluginconfpfx)
        ##         self.mm.loadModule(name)

        observer = site.get_site(options.sitename)

        scheduler = Scheduler(logger, observer)

        model = QueueModel(logger, scheduler)

        if options.completed is not None:
            # specify a list of completed OB keys
            with open(options.completed, 'r') as in_f:
                buf = in_f.read()
            import ast
            model.completed_obs = ast.literal_eval(buf)

        # Start up the control/display engine
        qplanner = QueuePlanner(logger, thread_pool, mm,
                                prefs, ev_quit, model)
        qplanner.set_input_dir(options.input_dir)
        qplanner.set_input_fmt(options.input_fmt)

        # Build desired layout
        qplanner.build_toplevel(default_layout)
        for w in qplanner.ds.toplevels:
            w.show()

        # load plugins
        for bnch in plugins:
            qplanner.load_plugin(bnch.name, bnch)

        qplanner.ds.raise_tab('Control Panel')

        guiHdlr = GuiLogHandler(qplanner)
        #guiHdlr.setLevel(options.loglevel)
        guiHdlr.setLevel(logging.INFO)
        fmt = logging.Formatter(log.LOG_FORMAT)
        guiHdlr.setFormatter(fmt)
        logger.addHandler(guiHdlr)

        qplanner.update_pending()

        # Did user specify geometry
        if options.geometry:
            qplanner.set_geometry(options.geometry)

        # Raise window
        w = qplanner.w.root
        w.show()

        server_started = False

        # Create threadpool and start it
        try:
            # Startup monitor threadpool
            thread_pool.startall(wait=True)

            try:
                # if there is a network component, start it
                if hasattr(qplanner, 'start'):
                    task = Task.FuncTask2(qplanner.start)
                    thread_pool.addTask(task)

                # Main loop to handle GUI events
                qplanner.mainloop(timeout=0.001)

            except KeyboardInterrupt:
                logger.error("Received keyboard interrupt!")

        finally:
            logger.info("Shutting down...")
            thread_pool.stopall(wait=True)

        sys.exit(0)


def planner(sys_argv):

    viewer = QueuePlanner(layout=default_layout)
    viewer.add_plugins(plugins)

    # Parse command line options with optparse module
    from optparse import OptionParser

    usage = "usage: %prog [options] cmd [args]"
    optprs = OptionParser(usage=usage,
                          version=('%%prog %s' % version.version))
    viewer.add_default_options(optprs)

    (options, args) = optprs.parse_args(sys_argv[1:])

    if options.display:
        os.environ['DISPLAY'] = options.display

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('viewer.main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print(("%s profile:" % sys_argv[0]))
        profile.run('viewer.main(options, args)')

    else:
        viewer.main(options, args)


# END
