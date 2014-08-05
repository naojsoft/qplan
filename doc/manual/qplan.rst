++++++++++++++++++++++++++++++++++++++++
How to use the Queue Simulation software
++++++++++++++++++++++++++++++++++++++++

Installing the software
-----------------------

The software currently requires Python 2.7 plus a few packages,
including matplotlib, ephem and ginga.

For Windows or Macintosh, the "Anaconda" distribution contains most of
what you need to run scientific python applications.  Install this and
then from a terminal do::

    $ pip install ginga
    $ pip install ephem

Finally you will need to install one module from source.  Best to clone
this with git:: 

    $ mkdir ~/Git
    $ cd ~/Git
    $ git clone git://ocsapp.subaru.nao.ac.jp/Observer
    $ cd Observer
    $ python setup.py install

Lastly we need our queue simulation software::

    $ cd ~/Git
    $ git clone git://ocsapp.subaru.nao.ac.jp/queuesim


Input files
-----------

A set of input files is necessary to define the parameters of the
simulation as a series of records in tables.  The format of the input
files is Comma Separated Value (CSV) table format.  These can be
exported from regular spreadsheets. Initially, we are using LibreOffice
to edit the spreadsheets and then export as CSV for the program.  Later
on we may develop other GUIs to produce the records.

The following files are defined:

- `programs.csv`
  This defines all the accepted programs for the semester.  Important
  columns include a proposal id, and an overall rank for each program.

- `schedule.csv`
  This defines all the runs of the semester, the filters available in
  each run, and the observed seeing and sky conditions for each night.

In addition to these main two files, there is a separate file for each
proposal that was accepted, named after the proposal id.  For example, 
"S10B-130.csv".  If there are twenty proposals accepted then there will
be twenty such files.  Each of these files contains all the Observation
Blocks (hereafter called "OBs") defined by the observer for their
observation.  An observation block defines a minimum schedulable unit of
observation. For SPCAM and  HSC, this usually means one dithered
exposure. 

An OB combines a telescope configuration, an instrument configuration,
an environment configuration (which contains constraints) and a target
configuration.

Information from all these files is used to create the schedule.

These files will be made available to you either from a google drive
link or via a local download.  Untar the files into a directory.

Running the software
--------------------

At present we are just running the software from a terminal::

    $ cd queuesim
    $ ./qplan.py

A GUI should appear on your display.  It might appear behind some other
windows (an oversight that will be fixed in the next release) so move
some windows around if you don't see it right away.

Initializing the simulation
---------------------------

In the upper right-hand side of the simulation GUI you will see the
"Control Panel".  In addition to the files, this provides the main
inputs for the simulation.

In the box labelled "Inputs:", type the path to the directory containing
the CSV simulation input files.  Then click "Load Info".  If everything
went well you should be able to click on the "Log" tab and see some
messages to the effect that: a) the schedule was read, b) the proposals
were read and, c) the OBs were loaded.

Running the simulation
----------------------

Finally we are ready to run the simulation.  Click "Build Schedule".
The Log should begin to fill up with messages about checking the OBs and
scheduling the OBs over the semester.  This process takes a little while
to run and while it is running the GUI controls may not be very
responsive to user actions.  Eventually the nights of the semester
should appear as dates in the left hand panel.  When the whole semester
has been scheduled, the Log will complete with a summary report, giving
the rate of completed and uncompleted programs.

After the simulation has run, you can click any date in the left column
to see the schedule for that night.  This will adjust the content in
three tabs:

- `Report` gives a schedule breakdown for the night.  It tells the time
  that an OB should execute, what program it belongs to (with rank), the
  time needed to run that OB, the filter used, desired airmass and
  target/comment. 

- `AirMass Chart` shows the rise/fall of each target for the night and
  showing the maximum airmass reached.

- `Slew Chart` shows each target plotted on a polar projection of the
  sky, so that the telescope slews can be judged.

-----------------------
Notes on the simulation
-----------------------

Pass/Fail criteria
------------------

OBs are fitted to the schedule according to criteria stored in each
OB--some of which are absolute pass/fail and some of which are weighted.

Currently, the constraints that are considered absolute are:

- filter (OB filter must match one of the filters available for the
  night as specified in the schedule)

- desired airmass (target airmass must be equal or less than the one
  specified in the OB)

- sky condition (OB value of "clear" (photometric) must match "clear" in
  schedule; OB value of "cirrus" matches clear/cirrus in schedule, and
  OB value of "any" matches anything in schedule)

- moon/target illumination (OB value of "dark", must mach 25% or less
  moon illumination--everything else is considered "grey" since we don't
  schedule SPCAM or HSC on bright nights)

Notes on the weights
--------------------

If an OB passes all of the absolute ("pass/fail") criteria for a night
slot, then the weighted factors come into play.  OBs are evaluated for
the slot and the "lightest" OB is the one chosen for the spot.  

The weights are calculated by the weighted sum of normalized factors.
The weights can be seen in the upper part of the control panel.  The
larger a weight is, the more "importance" is given to that factor.  
This technique allows for a kind of fuzzy logic to be applied; i.e. is it
better to observe an 8.0 ranked target, or change filters and
observe a 9.0 ranked target?  How about observing two 8.0 ranked targets
with 30 minute OBs now, or wait ten minutes and observe a 9.0 ranked
target with a 60 minute OB?  By adjusting the weights, we can influence
the decision making process.

The description of these weights is as follows:

- `slew weight` is the idea that shorter slews to new targets are better
  than longer slews.

- `delay weight` is the idea that shorter waits for a new target are
  better than longer waits.  For example, if a target can be observed
  immediately, this is better.

- `filter weight` is the idea that not changing filters is better than
  changing filters, since changing filters takes time, and has some risk
  associated with it.

- `rank weight` is the idea that an OB connected to a highly ranked
  program is better than one connected to a lower ranked program.

- `priority weight` is the idea that, *between two OBs belonging to the
  same proposal*, the one with a higher priority field is better than
  one with a lower priority field.  This criterion allows observers to
  prioritize their OBs for their particular program.

Changing the simulation
-----------------------

To rerun the simulation with different weights, simply change any of the
weights and click "Build Schedule".

To change the simulation data, open the CSV file with an editor and change
any of the desired fields in any of the files/records.  You can use a text
editor directly on the CSV file, or open the CSV file with a spreadsheet
program.  Save the file, then click "Load Info", verify the simulation
records loaded correctly in the Log, then click "Build Schedule".



