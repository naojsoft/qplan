#! /usr/bin/env python
#
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
from ginga.version import version
import os

srcdir = os.path.dirname(__file__)

from distutils.command.build_py import build_py

setup(
    name = "qplan",
    version = version,
    author = "Software Division, OCS Team",
    author_email = "ocs@naoj.org",
    description = ("Queue Observation Planner for Subaru Telescope."),
    long_description = 'README.txt',
    license = "BSD",
    keywords = "astronomy queue planner subaru telescope",
    url = "http://naojsoft.github.com/qplan",
    packages = ['qplan',
                # Misc
                'qplan.plots', 'qplan.plugins', 'qplan.util',
                # tests
                'qplan.tests',
                ],
    package_data = { 'qplan.doc': ['manual/*.rst'],
                     },
    scripts = ['scripts/qplan', 'scripts/qexec.py'],
    install_requires = ['pandas>=0.13.1', 'ginga>=2.5',
                        'matplotlib>=1.3.1'],
    #test_suite = "",
    classifiers=[
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: BSD License',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: C',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.5',
          'Topic :: Scientific/Engineering :: Astronomy',
          'Topic :: Scientific/Engineering :: Physics',
          ],
    cmdclass={'build_py': build_py}
)
