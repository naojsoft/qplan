++++++++++++++++++++++++++++++++++++++++
How to use the queue planning software
++++++++++++++++++++++++++++++++++++++++

Installing the software
-----------------------

The Queue Planning software currently requires Python 3.6 or newer
plus a few packages, including astropy, matplotlib, ephem, and ginga.

For Linux, Windows, or Macintosh, we recommend that you use the
"Anaconda - Individual Edition" Python distribution or the Miniconda
Python distribution, available from the following URL's:

  `Anaconda`: https://www.anaconda.com/products/individual

  `Miniconda`: https://docs.conda.io/en/latest/miniconda.html

Either one of the above distributions will allow you to set up a
Python environment in your own user directory without requiring any
system administrator privileges.

Follow the instructions from one of the above URL's to install either
Anaconda or Miniconda (choose one or the other - you don't need both).

The next step is to create a Python environment with the packages
required by qplan. Run the following commands in a terminal window::

  $ conda create -y -n qplan python=3.6 astropy ephem matplotlib numpy openpyxl pandas pyqt python-dateutil pytz qtpy xlrd
  $ conda install -n qplan -c astropy ginga

The next step is to download and install the qplan software::

  $ conda activate qplan
  $ git clone https://github.com/naojsoft/qplan
  $ cd ./qplan
  $ python setup.py install

At this point, you should be able to run qplan::

  $ conda activate qplan
  $ qplan

The qplan GUI should appear on your desktop.

Input files
-----------

A set of input files is necessary to define the parameters of the
observations as a series of records in tables. The format of the input
files is Excel spreadsheet files. Either the older Excel .xls or newer
.xlsx format is ok.

The following files are defined:

- `programs.xlsx`
  This defines all the accepted programs for the semester.  Important
  columns include a proposal id, and an overall rank for each program.

- `schedule.xlsx`
  This defines all the runs of the semester, the filters available in
  each run, and the observed seeing and sky conditions for each night.

- `weights.xlsx`
  This defines relative weights of the constraints to be used to
  determine the optimal schedule.

In addition to these main two files, there is a separate file for each
proposal that was accepted, named after the proposal id. For example,
"S10B-130.xlsx". If there are twenty proposals accepted then there
will be twenty such files.  Each of these files contains all the
Observation Blocks (hereafter called "OBs") defined by the observer
for their observation. An observation block defines a minimum
schedulable unit of observation. For SPCAM and HSC, this usually means
one dithered exposure.

An OB combines a telescope configuration, an instrument configuration,
an environment configuration (which contains constraints) and a target
configuration.

Information from all these files is used to create the schedule.

These files will be made available to you either from a google drive
link or via a local download.  Untar the files into a directory.

Running the software
--------------------

At present we are running the software from a terminal::

    $ conda activate qplan
    $ qplan --stderr -i <directory path to Excel input files>

A GUI should appear on your display.

Initializing the queue scheduling
---------------------------------

In the upper right-hand side of the simulation GUI you will see the
"Control Panel".  In addition to the files, this provides the main
inputs for the simulation.

In the box labelled "Inputs:", you should see the path to the
directory containing the Excel input files. Click the "Load Info"
button.  If everything went well, you should see that the "Weights",
"Schedule", and "Programs" tabs appeared in the pane in the top-center
of the GUI. Those three tabs should all be populated with the contents
read in from their respective Excel files.


Creating the schedule
---------------------

Finally we are ready to create the schedule.  Click "Build Schedule".
This process takes a little while to run and while it is running the
GUI controls may not be very responsive to user actions.  Eventually
the nights of the semester should appear as dates in the left hand
panel. When the entire semester has been scheduled, the terminal
window from which you ran qplan will show a summary report, giving the
rate of completed and uncompleted programs.

After the scheduling process has run, you can click any date in the
left column to see the schedule for that night.  This will adjust the
content in three tabs:

- `Report` gives a schedule breakdown for the night.  It tells the time
  that an OB should execute, what program it belongs to (with rank), the
  time needed to run that OB, the filter used, desired airmass and
  target/comment.

- `AirMass Chart` shows the rise/fall of each target for the night and
  showing the maximum airmass reached.

- `Slew Chart` shows each target plotted on a polar projection of the
  sky, so that the telescope slews can be judged.

-----------------------
Notes on the scheduling
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

Notes on the schedule file
--------------------------

The first three columns in the schedule file can be a bit confusing so
they deserve some explanation:

- `date` is the calendar date at the start of the observation night,
  expressed in the local time zone. An observation night normally
  begins just after sunset, so this would be the local date at
  sunset. This interpretation applies even if the queue observing
  begins after midnight, i.e., on the next calendar date.

- `start time` is the local time at the start of queue observing,
  i.e., the time at which you want the scheduler to start evaluting
  OB's for inclusion in the observation queue. This time can be before
  or after midnight. If "start time" is after midnight, it is
  interpreted as being on the next calendar date after the one
  specified in the "date" column.

- `end time` is the local time at the end of queue observing. The
  scheduler will make sure that all OB's have completed by this
  time. This time can be before or after midnight, but it should
  obviously be later than the "start time". If "stop time" is after
  midnight, it is interpreted as being on the next calendar date after
  the one specified in the "date" column.

Changing the scheduling
-----------------------

To rerun the scheduling with different weights, simply change any of
the weights and click "Build Schedule".

To change the scheduling data, open the Excel file with Excel or
LibreOffice and change any of the desired fields in any of the
files/records. Save the file using either the .xls or .xlsx format,
then click "Load Info", verify the updated records loaded correctly in
the respective tabs, then click "Build Schedule".

Builder
-------

The Builder tab in qplan can be used to generate a list of OB's
appropriate for any of the observing dates in the schedule.xlsx
file. Builder can schedule only nights that are specified in
schedule.xlsx because it uses schedule.xlsx to determine which filters
are available on any given night.

If you are running qplan on the Gen2 summit system, the "Update"
button on the Builder tab can be used to fetch from Gen2 the current
Az, El, and filter values to enable more efficient queue scheduling
based on actual current conditions.

For testing or simulation purposes, you can enter into the text boxes
your choices for the date, time, schedule length, etc. Note that the
"Local date" box should contain the calendar date in the local time
zone for when you want the schedule to begin. For scheduling that
starts before midnight, "Local date" will be the same date as in the
"date" column in schedule.xlsx. For start times after midnight, "Local
date" will be the following calendar date. The "Start Time" box in
Builder should contain the time, expressed in the local time zone,
when you want the schedule to begin.

Click on the "Get OB's" button to generate the list of OB's
appropriate to the conditions specified in the Builder tab. After the
schedule is created, you can click on any of the OB's in the result
and then the Airmass Chart and Slew Chart will update showing the OB's
target visibility and position on the sky, respectively.
