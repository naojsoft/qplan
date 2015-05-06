#
# summary.py -- creates summary plots
#
# Russell Kackley (rkackley@naoj.org)
#
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.font_manager import FontProperties
import matplotlib.patches as mpatches

import qsim

class BaseSumPlot(object):
    def __init__(self, width, height, dpi=96, logger=None):
        # create matplotlib figure
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.logger = logger
        self.barWidth = 0.5
        self.legendFont = FontProperties('sans-serif', 'normal', 'normal', 'normal', 'normal', 'small')
        self.bottomMargin = 0.15
        self.heightSpace = 0.6 # space between plots
        self.fig.subplots_adjust(bottom=self.bottomMargin, hspace=self.heightSpace)
        self.grades = ('A', 'B', 'C', 'F')
        self.grade_colors = {
            'A': 'green',
            'B': 'violet',
            'C': 'coral',
            'F': 'aqua',
            }
        self.activity_colors = {
            'Long slew':     'blue',
            'Filter change': 'cyan',
            'Delay':         'orchid',
            'Science':       'green',
            'Unscheduled':   'darkred'
            }

        self.ob_types = ('Long slew', 'Filter change', 'Delay', 'Science', 'Unscheduled')

    def clear(self):
        self.fig.clf()

    def get_figure(self):
        return self.fig

    # Override the plot method in subclass
    def plot(self):
        pass

class NightSumPlot(BaseSumPlot):
    # Make a bar chart to show which types of OB's will be executed
    # during the night

    def plot(self, schedules):
        # Create a plot that shows the activities (e.g., slews, filter
        # changes, etc.) for all the nights.
        plt = self.fig.add_subplot(111)
        plt.set_title('Nightly Activity')
        plt.set_xlabel('Minutes from start of night')

        # Iterate through all the dates in the schedules list. Note
        # that we iterate in reverse order so that the oldest dates
        # appear at the top of the plot, which is the same order as is
        # shown in the "Schedule" section on the left-hand side of
        # qplan/qexec.
        date_list = []
        for i, schedule in enumerate(list(reversed(schedules))):
            date_list.append(schedule.start_time.strftime('%Y-%m-%d'))
            y = [i]
            previous_slot_right = np.array([0.0])
            for slot in schedule.slots:
                ob = slot.ob
                dt = slot.stop_time - slot.start_time
                dt_minutes = dt.total_seconds() / 60.0
                width = np.array([dt_minutes])
                if ob is None:
                    ob_type = 'Unscheduled'
                else:
                    if ob.derived:
                        if 'Long slew' in ob.comment:
                            ob_type = 'Long slew'
                        elif 'Filter change' in ob.comment:
                            ob_type = 'Filter change'
                        elif 'Delay' in ob.comment:
                            ob_type = 'Delay'
                        else:
                            ob_type = 'Science'
                    else:
                        ob_type = 'Science'

                bar = plt.barh(y, width, self.barWidth, left=previous_slot_right, color=self.activity_colors[ob_type])
                previous_slot_right += width

        # Add the y-axis titles, which are the dates from the
        # schedules list.
        y = np.arange(len(schedules))
        plt.set_yticks(y+self.barWidth/2.)
        plt.set_yticklabels(date_list)

        # Reduce the plot area by a little bit so that we have room
        # for the legend outside the plot.
        box = plt.get_position()
        plt.set_position([box.x0, box.y0, box.width * 0.9, box.height])

        # Create some matplotlib "Patches" so that we can use them in
        # the legend
        legend_patches = []
        legend_titles = []
        for ob_type in self.ob_types:
            legend_patches.append(mpatches.Patch(color=self.activity_colors[ob_type]))
            legend_titles.append(ob_type)

        # Add a legend to the plot. We put the legend outside the plot
        # area so that we don't obscure any of the bars.
        plt.legend(legend_patches, legend_titles, prop=self.legendFont, loc='center left', bbox_to_anchor=(1, 0.5), handlelength=1)

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()

class ProposalSumPlot(BaseSumPlot):
    # Make a bar chart to show the completed OB percentage for each
    # proposal.
    def plot(self, completed, uncompleted):
        plt = self.fig.add_subplot(111)
        plt.set_title('Proposal Completion Percentage')
        plt.set_ylabel('OB Percent Complete')
        ind = np.arange(len(completed)+len(uncompleted))
        propID_comp_percent = {}
        grades_dict = {}
        for grade in self.grades:
            grades_dict[grade] = []
        for i, proposal in enumerate(completed+uncompleted):
            #x = [i]
            total_ob_count = float(proposal.obcount)
            uncompleted_count = len(proposal.obs)
            completed_count = float(total_ob_count - uncompleted_count)
            propID = str(proposal.pgm)
            propID_comp_percent[propID] = completed_count / total_ob_count * 100.0
            if propID not in grades_dict[proposal.pgm.grade]:
                grades_dict[proposal.pgm.grade].append(propID)

        # For the bar chart, we want all proposals grouped into their
        # "grade" category and then, within that category, sort the
        # proposals by their proposal ID.
        propid_list = []
        comp_percent = []
        colors = []
        for grade in self.grades:
            for propID in sorted(grades_dict[grade]):
                propid_list.append(propID)
                comp_percent.append(propID_comp_percent[propID])
                colors.append(self.grade_colors[grade])

        plt.bar(ind, comp_percent, self.barWidth, color=colors)
        plt.set_xticks(ind+self.barWidth/2.)
        plt.set_xticklabels(propid_list, rotation=45, ha='right')

        # Create some matplotlib "Patches" so that we can use them in
        # the legend
        legend_patches = []
        legend_titles = []
        for grade in self.grades:
            legend_patches.append(mpatches.Patch(color=self.grade_colors[grade]))
            legend_titles.append(grade)

        plt.legend(legend_patches, legend_titles, prop=self.legendFont, title='Grades', loc='center left', bbox_to_anchor=(1, 0.5), handlelength=1)

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()

class ScheduleSumPlot(BaseSumPlot):
    # Makes a bar chart to show scheduled/unscheduled minutes for each
    # night
    def plot(self, schedules):
        plt = self.fig.add_subplot(111)
        plt.set_title('Nightly Schedules')
        plt.set_ylabel('Time (min)')
        ind = np.arange(len(schedules))
        date_list = []
        sched_minutes = []
        unsched_minutes = []
        for schedule in schedules:
            date_list.append(schedule.start_time.strftime('%Y-%m-%d'))
            time_avail = schedule.stop_time - schedule.start_time
            time_avail_minutes = time_avail.total_seconds() / 60.0
            time_waste_minutes = qsim.eval_schedule(schedule).time_waste_sec / 60.0
            sched_minutes.append(time_avail_minutes - time_waste_minutes)
            unsched_minutes.append(time_waste_minutes)
        self.logger.debug('ind %s' % ind)
        self.logger.debug('date_list %s' % date_list)
        self.logger.debug('sched_minutes %s' % sched_minutes)
        self.logger.debug('unsched_minutes %s' % unsched_minutes)
        sched_bar = plt.bar(ind, sched_minutes, self.barWidth, color='g')
        unsched_bar = plt.bar(ind, unsched_minutes, self.barWidth, color='darkred', bottom=sched_minutes)
        plt.set_xticks(ind+self.barWidth/2.)
        plt.set_xticklabels(date_list, rotation=45, ha='right')
        plt.legend((unsched_bar, sched_bar), ('Delay+Unscheduled', 'Scheduled'), prop=self.legendFont)

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()

class SemesterSumPlot(BaseSumPlot):
    # Makes a pie chart to show percentage of available time allocated
    # to each proposal and also the unscheduled time.
    def plot(self, schedules):
        plt = self.fig.add_subplot(111)
        total_time_avail = 0.
        total_time_waste = 0.
        propID_alloc_minutes = {}
        grades_dict = {}
        for grade in self.grades:
            grades_dict[grade] = []
        for schedule in schedules:
            time_avail = schedule.stop_time - schedule.start_time
            time_avail_minutes = time_avail.total_seconds() / 60.0
            time_waste_minutes = qsim.eval_schedule(schedule).time_waste_sec / 60.0
            total_time_avail += time_avail_minutes
            total_time_waste += time_waste_minutes
            for slot in schedule.slots:
                ob = slot.ob
                if ob is not None:
                    propID = str(ob.program)
                    if propID not in grades_dict[ob.program.grade]:
                        grades_dict[ob.program.grade].append(propID)
                    if propID in propID_alloc_minutes:
                        propID_alloc_minutes[propID] += ob.total_time / 60.0
                    else:
                        propID_alloc_minutes[propID] = ob.total_time / 60.0

        total_time_sched = total_time_avail - total_time_waste
        self.logger.debug('propID_alloc_minutes %s' % propID_alloc_minutes)
        self.logger.debug('total_time_sched %f' % total_time_sched)
        self.logger.debug('total_time_waste %f' % total_time_waste)

        # For the pie chart, we want all proposals grouped into their
        # "grade" category and then, within that category, sort the
        # proposals by their proposal ID.
        labels = []
        sizes = []
        colors = []
        for grade in self.grades:
            for propID in sorted(grades_dict[grade]):
                labels.append(propID)
                sizes.append(propID_alloc_minutes[propID])
                colors.append(self.grade_colors[grade])

        labels.append('Unscheduled')
        sizes.append(total_time_waste)
        colors.append('darkred')
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%', shadow=True)
        semester, ident = labels[0].split('-')
        plt.set_title('Total for Semester %s = %5.0f Hours' % (semester, total_time_avail / 60.0))

        # Create some matplotlib "Patches" so that we can use them in
        # the legend
        legend_patches = []
        legend_titles = []
        for grade in self.grades:
            legend_patches.append(mpatches.Patch(color=self.grade_colors[grade]))
            legend_titles.append(grade)

        plt.legend(legend_patches, legend_titles, prop=self.legendFont, title='Grades', loc='center left', bbox_to_anchor=(1, 0.5), handlelength=1)

        canvas = self.fig.canvas
        if canvas is not None:
            canvas.draw()
