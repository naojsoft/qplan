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
from qplan import __version__

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
                      ['hpanel', dict(height=520),
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
          ptype='global', tab='Slew Chart', workspace='sub2', start=True,
          enabled=True),
    Bunch(name='report', module='Report', klass='Report',
          ptype='global', tab='Report', workspace='sub1', start=True,
          enabled=True),
    Bunch(name='ppcreport', module='PPCReport', klass='PPCReport',
          ptype='global', tab='PPC Report', workspace='sub1', start=True,
          enabled=True),
    Bunch(name='airmasschart', module='AirMassChart', klass='AirMassChart',
          ptype='global', tab='Airmass Chart', workspace='sub1', start=True,
          enabled=True),
    Bunch(name='schedule', module='Schedule', klass='Schedule',
          ptype='global', tab='Schedule', workspace='left', start=True,
          enabled=True),
    Bunch(name='builder', module='Builder', klass='Builder',
          ptype='global', tab='Builder', workspace='report', start=True,
          enabled=True),
    Bunch(name='logger', module='Logger', klass='Logger',
          ptype='global', tab='Log', workspace='report', start=True,
          enabled=True),
    Bunch(name='cp', module='ControlPanel', klass='ControlPanel',
          ptype='global', tab='Control Panel', workspace='right', start=True,
          enabled=True),
    Bunch(name='night_activity', module='SumChart', klass='NightSumChart',
          ptype='global', tab='Night Activity Chart', workspace='sub1',
          start=True, enabled=True),
    Bunch(name='night_sched', module='SumChart', klass='SchedSumChart',
          ptype='global', tab='Schedules Chart', workspace='sub1', start=True,
          enabled=True),
    Bunch(name='proposals', module='SumChart', klass='ProposalSumChart',
          ptype='global', tab='Proposals Chart', workspace='sub1', start=True,
          enabled=True),
    Bunch(name='semester', module='SumChart', klass='SemesterSumChart',
          ptype='global', tab='Semester Chart', workspace='sub1', start=True,
          enabled=True),
    Bunch(name='errors', module='Errors', klass='Errors',
          ptype='global', tab='Errors', workspace='right', start=True,
          enabled=True),
    Bunch(name='command', module='Command', klass='Command',
          ptype='global', tab='Command', workspace='right', start=False,
          enabled=True),
    ]


class QueuePlanner:
    """
    This class exists solely to be able to customize the queue planner
    startup/application.
    """
    def __init__(self, layout=default_layout):
        self.plugins = []
        self.layout = layout
        self.ev_quit = None
        self.thread_pool = None
        self.prefs = None
        self.settings = None
        self.basedir = None

    def add_plugins(self, plugins):
        self.plugins.extend(plugins)

    def add_default_options(self, argprs):
        """
        Adds the default reference viewer startup options to an
        ArgumentParser instance `argprs`.
        """
        argprs.add_argument("-c", "--completed", dest="completed", default=None,
                            metavar="FILE",
                            help="Specify FILE of completed OB keys")
        argprs.add_argument("--date-start", dest="date_start", default=None,
                            help="Define the start of the schedule ('YYYY-MM-DD HH:MM')")
        argprs.add_argument("--date-stop", dest="date_stop", default=None,
                            help="Define the end of the schedule ('YYYY-MM-DD HH:MM')")
        argprs.add_argument("--display", dest="display", metavar="HOST:N",
                            help="Use X display on HOST:N")
        argprs.add_argument("-g", "--geometry", dest="geometry",
                            metavar="GEOM", default=None,
                            help="X geometry for initial size and placement")
        argprs.add_argument("-i", "--input", dest="input_dir", default=None,
                            metavar="DIRECTORY",
                            help="Read input files from DIRECTORY")
        argprs.add_argument("-f", "--format", dest="input_fmt", default=None,
                            metavar="FILE_FORMAT",
                            help="Specify input file format (csv, xls, or xlsx)")
        argprs.add_argument("--norestore", dest="norestore", default=False,
                            action="store_true",
                            help="Don't restore the GUI from a saved layout")
        ## argprs.add_argument("--modules", dest="modules", metavar="NAMES",
        ##                   help="Specify additional modules to load")
        argprs.add_argument("--numthreads", dest="numthreads", type=int,
                            default=30,
                            help="Start NUM threads in thread pool", metavar="NUM")
        argprs.add_argument("-o", "--output", dest="output_dir", default=None,
                            metavar="DIRECTORY",
                            help="Write output files to DIRECTORY")
        argprs.add_argument("-s", "--site", dest="sitename", metavar="NAME",
                            default=None,
                            help="Observing site NAME")
        argprs.add_argument("-t", "--toolkit", dest="toolkit", metavar="NAME",
                            default=None,
                            help="Prefer GUI toolkit (default: choose one)")
        argprs.add_argument('--version', action='version',
                            version='%(prog)s v{version}'.format(version=__version__),
                            help="Show the qplan version and exit")
        log.addlogopts(argprs)


    def main(self, options, args):
        # Create top level logger.
        svcname = 'qplan'
        self.logger = log.get_logger(name=svcname, options=options)
        self.logger.info("starting qplan %s" % (version.version))

        self.ev_quit = threading.Event()
        self.layout = default_layout
        self.plugins = plugins

        # Get settings folder
        if ('CONFHOME' in os.environ and
            len(os.environ['CONFHOME'].strip()) > 0):
            basedir = os.path.join(os.environ['CONFHOME'], svcname)
        else:
            basedir = os.path.join(os.environ['HOME'], '.' + svcname)
        if not os.path.exists(basedir):
            os.mkdir(basedir)
        self.prefs = Settings.Preferences(basefolder=basedir,
                                          logger=self.logger)
        self.basedir = basedir

        settings = self.prefs.create_category('general')
        settings.load(onError='silent')
        settings.set_defaults(output_dir=options.output_dir,
                              widgetSet='choose',
                              recursion_limit=2000,
                              min_threads=2,
                              num_threads=max(os.cpu_count(), 10),
                              sitename='subaru',
                              input_dir='.',
                              completed_file=None,
                              input_format=None,
                              # this only takes effect if we are using
                              # the pgwidgets backend
                              http_server=True,
                              geometry='1440x900',
                              confirm_shutdown=True,
                              save_layout=True)
        self.settings = settings

        # ------ command line overrides for various settings -----
        #
        if hasattr(options, 'toolkit') and options.toolkit is not None:
            settings.set(widgetSet=options.toolkit)

        # number of threads
        if hasattr(options, 'numthreads') and options.numthreads is not None:
            settings.set(num_threads=options.numthreads)

        # did user specify a particular geometry?
        if hasattr(options, 'geometry') and options.geometry is not None:
            settings.set(geometry=options.geometry)

        # did user specify a particular site?
        if hasattr(options, 'sitename') and options.sitename is not None:
            settings.set(sitename=options.sitename)

        # restore the window to approximate
        if hasattr(options, 'norestore'):
            settings.set(ignore_saved_layout=options.norestore)

        # set input directory
        if hasattr(options, 'input_dir') and options.input_dir is not None:
            settings.set(input_dir=options.input_dir)

        # set input format
        if hasattr(options, 'input_fmt') and options.input_fmt is not None:
            settings.set(input_format=options.input_fmt)

        # set completed file
        if hasattr(options, 'completed') and options.completed is not None:
            settings.set(completed_file=options.completed)

        # --------------------------------------------------------

        self.setup()

        # process non-option command line args
        #self.process_args(args)

        # run the app event loop
        self.run()

    def setup(self):
        self.thread_pool = Task.ThreadPool(logger=self.logger,
                                           ev_quit=self.ev_quit,
                                           minthreads=self.settings.get('min_threads'),
                                           numthreads=self.settings.get('num_threads'))

        toolkit = self.settings.get('widgetSet', 'choose')
        if toolkit != 'choose':
            ginga_toolkit.use(toolkit)
        else:
            ginga_toolkit.choose()

        tkname = ginga_toolkit.get_family()
        self.logger.info("Chosen toolkit (%s) family is '%s'" % (
            ginga_toolkit.toolkit, tkname))

        from qplan.View import Viewer
        # must import AFTER Viewer
        from ginga.rv.Control import GuiLogHandler

        class QueuePlanner(Controller, Viewer):

            def __init__(self, logger, thread_pool, module_manager, preferences,
                         ev_quit, model, ws_sock=None):

                # Create general preferences
                self.prefs = preferences
                settings = self.prefs.create_category('general')
                settings.set(appname='qplan')
                Viewer.__init__(self, logger, thread_pool, settings, ev_quit,
                                ws_sock=ws_sock)
                Controller.__init__(self, logger, thread_pool, module_manager,
                                    preferences, ev_quit, model)

        mm = ModuleManager.ModuleManager(self.logger)

        observer = site.get_site(self.settings.get('sitename'))

        scheduler = Scheduler(self.logger, observer)

        model = QueueModel(self.logger, scheduler)

        completed_file = self.settings.get('completed_file', None)
        if completed_file is not None:
            import json
            self.logger.info("reading executed OBs from '{}' ...".format(completed_file))
            # user specified a set of completed OB keys
            with open(completed_file, 'r') as in_f:
                buf = in_f.read()
            d = json.loads(buf)
            model.completed_obs = {(propid, obcode): d[propid][obcode]
                                   for propid in d
                                   for obcode in d[propid]}

        # Start up the control/display engine
        qplanner = QueuePlanner(self.logger, self.thread_pool, mm,
                                self.prefs, self.ev_quit, model)
        qplanner.set_input_dir(self.settings.get('input_dir'))
        qplanner.set_input_fmt(self.settings.get('input_format'))
        self.qplanner = qplanner

        layout_file = None
        norestore = self.settings.get('ignore_saved_layout', False)
        if not norestore and self.settings.get('save_layout', False):
            layout_file = os.path.join(self.basedir, 'layout.json')

        # Build desired layout
        qplanner.build_toplevel(default_layout, layout_file=layout_file)
        for w in qplanner.ds.toplevels:
            w.show()

        # load plugins
        for spec in self.plugins:
            qplanner.load_plugin(spec.name, spec)

        # start any plugins that have start=True
        qplanner.boot_plugins()

        qplanner.ds.raise_tab('Control Panel')

        guiHdlr = GuiLogHandler(qplanner)
        guiHdlr.setLevel(logging.INFO)
        fmt = logging.Formatter(log.LOG_FORMAT)
        guiHdlr.setFormatter(fmt)
        self.logger.addHandler(guiHdlr)

        qplanner.update_pending()

        # Did user specify a particular geometry?
        geometry = self.settings.get('geometry', None)
        if geometry is not None:
            qplanner.set_geometry(geometry)

        # Raise window
        w = qplanner.w.root
        w.set_title(f"QPlan v{__version__}")
        w.show()

    def run(self):
        server_started = False

        # Create threadpool and start it
        try:
            # Startup monitor threadpool
            self.thread_pool.startall(wait=True)

            try:
                # if there is a network component, start it
                if hasattr(self.qplanner, 'start'):
                    self.qplanner.start()

                if hasattr(self.qplanner, 'get_url'):
                    base_url = self.qplanner.get_url()
                    if base_url is not None:
                        print(f"visit {base_url} to view the application")
                        self.logger.info(f"visit {base_url} to view the application")

                # Main loop to handle GUI events
                self.logger.info("entering mainloop...")
                self.qplanner.mainloop(timeout=0.001)

            except KeyboardInterrupt:
                self.logger.error("Received keyboard interrupt!")

        finally:
            self.logger.info("Shutting down...")
            self.thread_pool.stopall(wait=True)

        sys.exit(0)


def planner(sys_argv):

    viewer = QueuePlanner(layout=default_layout)
    viewer.add_plugins(plugins)

    from argparse import ArgumentParser

    argprs = ArgumentParser(description="Queue Planner for Subaru Telescope")
    viewer.add_default_options(argprs)

    (options, args) = argprs.parse_known_args(sys_argv[1:])

    if options.version:
        from qplan import __version__
        print(f"QPlan {__version__}")
        sys.exit(0)

    if options.display:
        os.environ['DISPLAY'] = options.display

    viewer.main(options, args)
