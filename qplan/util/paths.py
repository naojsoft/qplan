import os
import pathlib

qplan_home = None

if ('CONFHOME' in os.environ and
    len(os.environ['CONFHOME'].strip()) > 0):
    qplan_home = pathlib.Path(os.environ['CONFHOME']) / 'qplan'
else:
    qplan_home = pathlib.Path(os.environ['HOME']) / '.qplan'
