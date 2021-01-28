#! /usr/bin/env python
#
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
from qplan.version import version
import os

srcdir = os.path.dirname(__file__)

from distutils.command.build_py import build_py

long_description = '''
qplan is the basis of Queue Planner software for Subaru Telescope.
'''

setup(
    name = "qplan",
    version = version,
    author = "Software Division, OCS Team",
    author_email = "eric@naoj.org",
    description = ("Queue Observation Planner for Subaru Telescope."),
    long_description = long_description,
    license = "BSD",
    keywords = "astronomy queue planner subaru telescope",
    url = "http://naojsoft.github.com/qplan",
    packages = ['qplan',
                # Misc
                'qplan.plots', 'qplan.plugins', 'qplan.util', 'qplan.cfg',
                # tests
                'qplan.tests',
                ],
    package_data = { 'qplan.doc': ['manual/*.rst'],
                     },
    scripts = ['scripts/qplan', 'scripts/qexec.py'],
    install_requires = ['pandas>=0.24.1', 'xlrd>=1.2.0', 'openpyxl>=3.0.5',
                        'ginga>=3.1', 'qtpy>=1.6.0',
                        'matplotlib>=2.2.3', 'ephem>=3.7.5.3',
                        'pyyaml>=5.3.1'],
    #test_suite = "",
    classifiers=[
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: BSD License',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: C',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.7',
          'Topic :: Scientific/Engineering :: Astronomy',
          'Topic :: Scientific/Engineering :: Physics',
          ],
    cmdclass={'build_py': build_py}
)
