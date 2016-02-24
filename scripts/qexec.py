#!/usr/bin/env python
#
# qexec.py -- Subaru Telescope Queue Execution Tool
#
"""
Usage:
    qexec.py --help
    qexec.py [options]
"""
import sys, os
from qplan import main, version

defaultServiceName = 'qexecute'

plugins = [
    # pluginName, moduleName, className, workspaceName, tabName
    ('slewchart', 'SlewChart', 'SlewChart', 'sub2', 'Slew Chart'),
    ('airmasschart', 'AirMassChart', 'AirMassChart', 'sub1', 'AirMass Chart'),
    ('schedule', 'Schedule', 'Schedule', 'left', 'Schedule'),
    ('execute', 'Execute', 'Execute', 'report', 'Execute'),
    ('logger', 'Logger', 'Logger', 'report', 'Log'),
    ('cp', 'ControlPanel', 'ControlPanel', 'right', 'Control Panel'),
    #('resolution', 'Resolution', 'Resolution', 'right', 'OB Resolution'),
    ('night_activity', 'SumChart', 'NightSumChart', 'sub1', 'Night Activity Chart'),
    ('night_sched', 'SumChart', 'SchedSumChart', 'sub1', 'Schedules Chart'),
    ('proposals', 'SumChart', 'ProposalSumChart', 'sub1', 'Proposals Chart'),
    ('semester', 'SumChart', 'SemesterSumChart', 'sub1', 'Semester Chart'),
    ]


if __name__ == "__main__":

    viewer = main.QueuePlanner(layout=main.default_layout)
    # use our version of plugins
    viewer.add_plugins(plugins)

    # Parse command line options with optparse module
    from optparse import OptionParser

    usage = "usage: %prog [options] cmd [args]"
    optprs = OptionParser(usage=usage,
                          version=('%%prog %s' % version.version))
    viewer.add_default_options(optprs)
    optprs.add_option("--svcname", dest="svcname", metavar="NAME",
                      default=defaultServiceName,
                      help="Register using NAME as service name")
    ## optprs.add_option("--monitor", dest="monitor", metavar="NAME",
    ##                   default='monitor',
    ##                   help="Synchronize from monitor named NAME")
    ## optprs.add_option("--monchannels", dest="monchannels",
    ##                   default='status', metavar="NAMES",
    ##                   help="Specify monitor channels to subscribe to")
    ## optprs.add_option("--monport", dest="monport", type="int",
    ##                   help="Register monitor using PORT", metavar="PORT")

    (options, args) = optprs.parse_args(sys.argv[1:])

    if options.display:
        os.environ['DISPLAY'] = options.display

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('viewer.main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print(("%s profile:" % sys.argv[0]))
        profile.run('viewer.main(options, args)')

    else:
        viewer.main(options, args)

# END
