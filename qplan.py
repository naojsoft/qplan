#!/usr/bin/env python
#
# qplan.py -- Queue simulation/scheduler
#
# Eric Jeschke (eric@naoj.org)
#
"""
Usage:
    qplan.py
"""

# stdlib imports
import sys, os
import threading
import logging

moduleHome = os.path.split(sys.modules[__name__].__file__)[0]
sys.path.insert(0, moduleHome)
pluginHome = os.path.join(moduleHome, 'plugins')
sys.path.insert(0, pluginHome)

# Subaru python stdlib imports
from ginga.misc import ModuleManager, Settings, Task, Bunch
from ginga.misc import log
from ginga.Control import GuiLogHandler

# Local application imports
from Control import Controller
from View import Viewer
from Model import QueueModel

version = "20140804.0"

defaultServiceName = 'queueplanner'

default_layout = ['seq', {},
                   ['vbox', dict(name='top', width=1400, height=900),
                    dict(row=['hbox', dict(name='menu')],
                         stretch=0),
                    dict(row=['hpanel', {},
                     ['ws', dict(name='left', width=300, show_tabs=False),
                      # (tabname, layout), ...
                      ], 
                     ['vpanel', {},
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
    # pluginName, moduleName, className, workspaceName, tabName
    ('slewchart', 'SlewChart', 'SlewChart', 'sub2', 'Slew Chart'),
    ('airmasschart', 'AirMassChart', 'AirMassChart', 'sub1', 'AirMass Chart'),
    ('schedule', 'Schedule', 'Schedule', 'left', 'Schedule'),
    ('report', 'Report', 'Report', 'report', 'Report'),
    ('logger', 'Logger', 'Logger', 'report', 'Log'),
    ('cp', 'ControlPanel', 'ControlPanel', 'right', 'Control Panel'),
    ]

class QueuePlanner(Controller, Viewer):

    def __init__(self, logger, threadPool, module_manager, preferences,
                 ev_quit, model):

        Viewer.__init__(self, logger, ev_quit)
        Controller.__init__(self, logger, threadPool, module_manager,
                            preferences, ev_quit, model)


def main(options, args):
    # Create top level logger.
    svcname = options.svcname
    logger = log.get_logger(name='qplan', options=options)

    ev_quit = threading.Event()

    threadPool = Task.ThreadPool(logger=logger, ev_quit=ev_quit,
                                 numthreads=options.numthreads)
    
    # Get settings folder
    ## if os.environ.has_key('CONFHOME'):
    ##     basedir = os.path.join(os.environ['CONFHOME'], svcname)
    ## else:
    basedir = os.path.join(os.environ['HOME'], '.' + svcname)
    if not os.path.exists(basedir):
        os.mkdir(basedir)
    prefs = Settings.Preferences(basefolder=basedir, logger=logger)

    mm = ModuleManager.ModuleManager(logger)

    ## # Add any custom modules
    ## if options.modules:
    ##     modules = options.modules.split(',')
    ##     for mdlname in modules:
    ##         #self.mm.loadModule(name, pfx=pluginconfpfx)
    ##         self.mm.loadModule(name)

    model = QueueModel(logger=logger)
    
    # Start up the control/display engine
    qplanner = QueuePlanner(logger, threadPool, mm, prefs, ev_quit, model)

    # Build desired layout
    qplanner.build_toplevel(default_layout)
    for w in qplanner.ds.toplevels:
        w.showNormal()

    for pluginName, moduleName, className, wsName, tabName in plugins:
        qplanner.load_plugin(pluginName, moduleName, className,
                             wsName, tabName)

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
    qplanner.app.setActiveWindow(w)
    w.raise_()
    w.activateWindow()

    server_started = False

    # Create threadpool and start it
    try:
        # Startup monitor threadpool
        threadPool.startall(wait=True)

        try:
            # Main loop to handle GUI events
            qplanner.mainloop(timeout=0.001)

        except KeyboardInterrupt:
            logger.error("Received keyboard interrupt!")

    finally:
        logger.info("Shutting down...")
        threadPool.stopall(wait=True)

    sys.exit(0)
        

if __name__ == "__main__":
   
    # Parse command line options with nifty new optparse module
    from optparse import OptionParser

    usage = "usage: %prog [options] cmd [args]"
    optprs = OptionParser(usage=usage, version=('%%prog %s' % version))
    
    optprs.add_option("--date-start", dest="date_start", default=None,
                      help="Define the start of the schedule ('YYYY-MM-DD HH:MM')")
    optprs.add_option("--date-stop", dest="date_stop", default=None,
                      help="Define the end of the schedule ('YYYY-MM-DD HH:MM')")
    optprs.add_option("--debug", dest="debug", default=False, action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("--display", dest="display", metavar="HOST:N",
                      help="Use X display on HOST:N")
    optprs.add_option("-g", "--geometry", dest="geometry",
                      metavar="GEOM", default="+20+100",
                      help="X geometry for initial size and placement")
    optprs.add_option("-i", "--input", dest="input_dir", default="input",
                      metavar="DIRECTORY",
                      help="Read input files from DIRECTORY")
    optprs.add_option("--log", dest="logfile", metavar="FILE",
                      help="Write logging output to FILE")
    optprs.add_option("--loglevel", dest="loglevel", metavar="LEVEL",
                      type='int', default=logging.INFO,
                      help="Set logging level to LEVEL")
    ## optprs.add_option("--modules", dest="modules", metavar="NAMES",
    ##                   help="Specify additional modules to load")
    ## optprs.add_option("--monitor", dest="monitor", metavar="NAME",
    ##                   default='monitor',
    ##                   help="Synchronize from monitor named NAME")
    ## optprs.add_option("--monchannels", dest="monchannels", 
    ##                   default='status', metavar="NAMES",
    ##                   help="Specify monitor channels to subscribe to")
    ## optprs.add_option("--monport", dest="monport", type="int",
    ##                   help="Register monitor using PORT", metavar="PORT")
    optprs.add_option("--numthreads", dest="numthreads", type="int",
                      default=30,
                      help="Start NUM threads in thread pool", metavar="NUM")
    optprs.add_option("-o", "--output", dest="output_dir", default="output",
                      metavar="DIRECTORY",
                      help="Write output files to DIRECTORY")
    ## optprs.add_option("--plugins", dest="plugins", metavar="NAMES",
    ##                   help="Specify additional plugins to load")
    ## optprs.add_option("--port", dest="port", type="int", default=None,
    ##                   help="Register using PORT", metavar="PORT")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    optprs.add_option("--svcname", dest="svcname", metavar="NAME",
                      default=defaultServiceName,
                      help="Register using NAME as service name")
    optprs.add_option("--stderr", dest="logstderr", default=False,
                      action="store_true",
                      help="Copy logging also to stderr")

    (options, args) = optprs.parse_args(sys.argv[1:])

    if options.display:
        os.environ['DISPLAY'] = options.display

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print "%s profile:" % sys.argv[0]
        profile.run('main(options, args)')


    else:
        main(options, args)

# END
