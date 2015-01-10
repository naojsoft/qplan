#
# Resolution.py -- Observing Block Resolution page
# 
# Russell Kackley (rkackley@naoj.org)
#
import os.path

from ginga.misc import Bunch
from ginga.misc import Widgets
from PyQt4 import QtGui, QtCore

import PlBase

class Resolution(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super(Resolution, self).__init__(model, view, controller, logger)
        self.oblist = []
        self.oblist_index = None
        self.ob_resolution = {}

    def build_gui(self, container):
        # Create a scrollable area
        sw = Widgets.ScrollArea()

        # Create a vertical box into which our widgets will be placed
        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        # Place the vertical box inside the scrollable area
        sw.set_widget(vbox)

        # Create a frame for the program name and the OB ID.
        prog_ob_frame = Widgets.Frame()
        # Create some label widgets to display the program and the OB
        # ID
        captions = (('Program:', 'label', 'Program', 'label',
                     'OB ID:', 'label', 'OB ID', 'label',
                     'Dup All OB', 'checkbutton'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_prog_ob = b
        # Set the inital text for the program and OB ID to N/A
        b.program.set_text('N/A')
        b.ob_id.set_text('N/A')
        b.dup_all_ob.set_state(True)

        # Place the label widgets into the frame
        prog_ob_frame.set_widget(w)
        # Add the frame to the vertical box
        vbox.add_widget(prog_ob_frame, stretch=0)

        # Create a frame for the resolution comments
        comment_frame = Widgets.Frame('OB Comments')

        # Create a text area into which comments can be entered
        captions = (('Comment entry', 'textarea'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_comments = b

        # Place the text area into the frame
        comment_frame.set_widget(w)
        # Add the frame to the vertical box
        vbox.add_widget(comment_frame, stretch=0)

        # Create a frame for the data quality buttons
        data_button_frame = Widgets.Frame()
        # Create some radio buttons to describe the data quality
        captions = (('Data Quality:', 'label',
                     'Good', 'radiobutton',
                     'Questionable', 'radiobutton',
                     'Bad', 'radiobutton'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_data_buttons = b

        b.good.add_callback('activated', self.good_cb);
        b.questionable.add_callback('activated', self.questionable_cb);
        b.bad.add_callback('activated', self.bad_cb);

        self.data_bg = QtGui.QButtonGroup()
        self.data_bg.addButton(self.w_data_buttons.good.get_widget())
        self.data_bg.addButton(self.w_data_buttons.questionable.get_widget())
        self.data_bg.addButton(self.w_data_buttons.bad.get_widget())

        # Place the radio buttons into the frame
        data_button_frame.set_widget(w)
        # Add the frame to the vertical box
        vbox.add_widget(data_button_frame, stretch=0)

        # Create a frame for the clear button
        clear_button_frame = Widgets.Frame()
        # Create the Clear button
        captions = (('Clear', 'button'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_clear = b

        # Connect the button-click event to the callback method
        b.clear.add_callback('activated', self.clear_cb)

        # Place the radio buttons into the frame
        clear_button_frame.set_widget(w)
        # Add the frame to the vertical box
        vbox.add_widget(clear_button_frame, stretch=0)

        # Create a frame for the slider bar
        slider_frame = Widgets.Frame()
        captions = (('ob list index', 'hscale'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_slider = b
        b.ob_list_index.set_limits(0, 1)
        b.ob_list_index.set_tracking(True)
        b.ob_list_index.add_callback('value-changed', self.ob_list_index_cb)
        # Place the slider bar into the frame
        slider_frame.set_widget(w)
        # Add the frame to the vertical box
        vbox.add_widget(slider_frame, stretch=0)

        # Create a frame for the first/prev/next/last buttons
        prev_next_button_frame = Widgets.Frame()
        # Create the First, Prev, Next, and Last buttons
        captions = (('First', 'button', 'Prev', 'button', 'Next', 'button', 'Last', 'button'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_prev_next = b

        # Connect the button-click event to the callback method
        b.first.add_callback('activated', self.first_cb)
        b.next.add_callback('activated', self.next_cb)
        b.prev.add_callback('activated', self.prev_cb)
        b.last.add_callback('activated', self.last_cb)

        # Place the radio buttons into the frame
        prev_next_button_frame.set_widget(w)
        # Add the frame to the vertical box
        vbox.add_widget(prev_next_button_frame, stretch=0)

        # Create a frame for the save buttons
        save_button_frame = Widgets.Frame()
        # Create the Save button
        captions = (('Save', 'button'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_save_button = b

        # Connect the button-click event to the callback method
        b.save.add_callback('activated', self.save_cb)

        # Place the button into the frame
        save_button_frame.set_widget(w)
        # Add the frame to the vertical box
        vbox.add_widget(save_button_frame, stretch=0)

        # Create a layout for the container that was supplied to us
        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # Set the supplied container to have the layout we just
        # created
        container.setLayout(layout)

        # Get the widget for the scrollable area
        top_w = sw.get_widget()

        # Add the widget for the scrollable area to the layout we just
        # created for the supplied container
        layout.addWidget(top_w, stretch=1)

    def set_data_quality(self, button, value):
        try:
            if self.oblist_index is not None:
                if self.w_prog_ob.dup_all_ob.get_state():
                    for ob in self.oblist:
                        self.ob_resolution[str(ob)][button] = value
                        self.logger.debug('ob %s %s is %s' % (str(ob), button, self.ob_resolution[str(ob)][button]))
                        if value:
                            ob.data_quality = button
                else:
                    ob = str(self.oblist[self.oblist_index])
                    self.ob_resolution[ob][button] = value
                    self.logger.debug('ob %s %s is %s' % (ob, button, self.ob_resolution[ob][button]))
                    if value:
                        self.oblist[self.oblist_index].data_quality = button
        except Exception as e:
            self.logger.error('Error in set_data_quality: %s %s %s' % (button, value, str(e)))

    def good_cb(self, widget, value):
        self.set_data_quality('Good', value)

    def questionable_cb(self, widget, value):
        self.set_data_quality('Questionable', value)

    def bad_cb(self, widget, value):
        self.set_data_quality('Bad', value)

    def save_cb(self, widget):
        try:
            self.save_comments()
            for ob in self.ob_resolution:
                cmt_text = self.ob_resolution[ob]['OB_Comments']
                good = self.ob_resolution[ob]['Good']
                questionable = self.ob_resolution[ob]['Questionable']
                bad = self.ob_resolution[ob]['Bad']
                self.logger.debug('ob %s cmt_text %s good %s quest %s bad %s' % (ob, cmt_text, good, questionable, bad))
            for ob in self.oblist:
                self.logger.debug('ob %s comment %s data_quality %s' % (ob, ob.comment, ob.data_quality))
        except Exception as e:
            self.logger.error('Error in save_cb: %s' % str(e))

    def clear_cb(self, widget):
        self.logger.info('clear clicked')
        try:
            if not self.ob_resolution[str(self.oblist[self.oblist_index])]['Special_Comment']:
                self.w_comments.comment_entry.clear()
            self.data_bg.setExclusive(False)
            self.w_data_buttons.good.set_state(False)
            self.w_data_buttons.questionable.set_state(False)
            self.w_data_buttons.bad.set_state(False)
            self.data_bg.setExclusive(True)
            if self.oblist_index is not None:
                ob = str(self.oblist[self.oblist_index])
                if not self.ob_resolution[str(self.oblist[self.oblist_index])]['Special_Comment']:
                    self.ob_resolution[ob]['OB_Comments'] = ''
                for button in ('Good', 'Questionable', 'Bad'):
                    self.ob_resolution[ob][button] = False
        except Exception as e:
            self.logger.error('Error in clear_cb: %s' % str(e))

    def save_comments(self):
        if self.oblist_index is not None:
            current_comment = self.w_comments.comment_entry.get_text()
            if not self.ob_resolution[str(self.oblist[self.oblist_index])]['Special_Comment']:
                if self.w_prog_ob.dup_all_ob.get_state():
                    for ob in self.oblist:
                        self.ob_resolution[str(ob)]['OB_Comments'] = current_comment
            else:
                self.ob_resolution[str(self.oblist[self.oblist_index])]['OB_Comments'] = current_comment

    def show_ob(self):
        try:
            ob = self.oblist[self.oblist_index]
            self.w_prog_ob.program.set_text(ob.program.proposal)
            self.w_prog_ob.ob_id.set_text(ob.id)
            resolution = self.ob_resolution[str(ob)]
            self.w_comments.comment_entry.set_text(resolution['OB_Comments'])
            self.data_bg.setExclusive(False)
            self.w_data_buttons.good.set_state(resolution['Good'])
            self.w_data_buttons.questionable.set_state(resolution['Questionable'])
            self.w_data_buttons.bad.set_state(resolution['Bad'])
            self.data_bg.setExclusive(True)
        except Exception as e:
            self.logger.error(str(e))

    def select_ob(self, position):
        try:
            if len(self.oblist) > 0:
                self.save_comments()
                if position == 'first':
                    self.oblist_index = 0
                    self.w_slider.ob_list_index.set_value(self.oblist_index)
                elif position == 'prev':
                    if self.oblist_index > 0:
                        self.oblist_index -= 1
                        self.w_slider.ob_list_index.set_value(self.oblist_index)
                elif position == 'next':
                    if self.oblist_index < len(self.oblist) - 1:
                        self.oblist_index += 1
                        self.w_slider.ob_list_index.set_value(self.oblist_index)
                elif position == 'last':
                    if len(self.oblist) > 0:
                        self.oblist_index = len(self.oblist) - 1
                        self.w_slider.ob_list_index.set_value(self.oblist_index)
                else:
                    self.oblist_index = position
                self.show_ob()
        except Exception as e:
            self.logger.error('Error in select_ob: %s' % str(e))

    def ob_list_index_cb(self, widget, value):
        self.select_ob(value)

    def first_cb(self, widget):
        self.select_ob('first')

    def prev_cb(self, widget):
        self.select_ob('prev')

    def next_cb(self, widget):
        self.select_ob('next')

    def last_cb(self, widget):
        self.select_ob('last')

    def resolve_obs(self, oblist):
        self.logger.debug('resolve_obs called oblist is %s len is %d' % (oblist, len(oblist)))
        self.oblist = oblist
        self.ob_resolution = {}
        if len(oblist) > 0:
            self.w_slider.ob_list_index.set_limits(0, len(oblist) - 1) 
            self.oblist_index = 0
            for ob in self.oblist:
                self.ob_resolution[str(ob)] = {}
                self.ob_resolution[str(ob)]['OB_Comments'] = ob.comment
                if ob.comment.startswith('Filter change') or \
                   ob.comment.startswith('Long slew') or \
                   ob.comment.startswith('Delay for'):
                    self.ob_resolution[str(ob)]['Special_Comment'] = True
                else:
                    self.ob_resolution[str(ob)]['Special_Comment'] = False
                for button in ('Good', 'Questionable', 'Bad'):
                    self.ob_resolution[str(ob)][button] = False
            self.show_ob()
        else:
            self.w_prog_ob.program.set_text('N/A')
            self.w_prog_ob.ob_id.set_text('N/A')
