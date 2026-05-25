#
# Resolution.py -- Observing Block Resolution page
#
# R. Kackley
#

from ginga.gw import Widgets

from . import PlBase


class Resolution(PlBase.Plugin):

    def __init__(self, model, view, controller, logger):
        super().__init__(model, view, controller, logger)
        self.oblist = []
        self.oblist_index = None
        self.ob_resolution = {}
        self.oblist_indices = []
        # These are the default quality buttons.  Subclasses can
        # override.
        self.qualityButtons = ('Good', 'Marginal', 'Bad')
        # Holds the cross-backend RadioButton wrappers so clear_cb
        # can iterate them.
        self.quality_radios = {}

    def build_gui(self, container):
        # Scrollable area holding all the editing widgets.
        sw = Widgets.ScrollArea()

        vbox = Widgets.VBox()
        vbox.set_border_width(4)
        vbox.set_spacing(2)
        sw.set_widget(vbox)

        # ----- Program / OB ID frame -------------------------------
        prog_ob_frame = Widgets.Frame()
        captions = (('Program:', 'label', 'Program', 'label',
                     'OB ID:', 'label', 'OB ID', 'label',
                     'Dup All OB', 'checkbutton'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_prog_ob = b
        b.program.set_text('N/A')
        b.ob_id.set_text('N/A')
        b.dup_all_ob.set_state(False)
        prog_ob_frame.set_widget(w)
        vbox.add_widget(prog_ob_frame, stretch=0)

        # ----- OB Comments frame -----------------------------------
        comment_frame = Widgets.Frame('OB Comments')
        captions = (('Comment entry', 'textarea'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_comments = b
        comment_frame.set_widget(w)
        vbox.add_widget(comment_frame, stretch=0)

        # ----- Data Quality radio buttons --------------------------
        #
        # We construct RadioButtons directly (instead of via
        # build_info) so we can pass ``group=`` to link them.  That
        # makes them exclusive across all four backends: gtk3, gtk4,
        # and pgw all honour the group; qtw ignores it but Qt's
        # built-in autoExclusive (default-on for QRadioButton
        # siblings sharing a parent) covers that case.
        data_button_frame = Widgets.Frame()
        dq_outer = Widgets.VBox()
        dq_outer.set_spacing(2)
        dq_outer.add_widget(Widgets.Label('Data Quality:'), stretch=0)
        dq_row = Widgets.HBox()
        dq_row.set_spacing(8)
        self.qualityButtonVals = {}
        first_radio = None
        for i, name in enumerate(self.qualityButtons):
            rb = Widgets.RadioButton(name, group=first_radio)
            if first_radio is None:
                first_radio = rb
            self.qualityButtonVals[name] = len(self.qualityButtons) - i
            self.quality_radios[name] = rb
            rb.add_callback('activated', self.rate_cb,
                            self.qualityButtonVals[name])
            dq_row.add_widget(rb, stretch=0)
        dq_row.add_widget(Widgets.Label(''), stretch=1)  # spacer
        dq_outer.add_widget(dq_row, stretch=0)
        data_button_frame.set_widget(dq_outer)
        vbox.add_widget(data_button_frame, stretch=0)

        # ----- Clear button ----------------------------------------
        clear_button_frame = Widgets.Frame()
        captions = (('Clear', 'button'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_clear = b
        b.clear.add_callback('activated', self.clear_cb)
        clear_button_frame.set_widget(w)
        vbox.add_widget(clear_button_frame, stretch=0)

        # ----- Slider for OB index ---------------------------------
        slider_frame = Widgets.Frame()
        captions = (('ob list index', 'hscale'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_slider = b
        b.ob_list_index.set_limits(0, 1)
        b.ob_list_index.set_tracking(True)
        b.ob_list_index.add_callback('value-changed', self.ob_list_index_cb)
        slider_frame.set_widget(w)
        vbox.add_widget(slider_frame, stretch=0)

        # ----- First/Prev/Next/Last buttons ------------------------
        prev_next_button_frame = Widgets.Frame()
        captions = (('First', 'button', 'Prev', 'button',
                     'Next', 'button', 'Last', 'button'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_prev_next = b
        b.first.add_callback('activated', self.first_cb)
        b.next.add_callback('activated', self.next_cb)
        b.prev.add_callback('activated', self.prev_cb)
        b.last.add_callback('activated', self.last_cb)
        prev_next_button_frame.set_widget(w)
        vbox.add_widget(prev_next_button_frame, stretch=0)

        # ----- Save button -----------------------------------------
        save_button_frame = Widgets.Frame()
        captions = (('Save', 'button'),)
        w, b = Widgets.build_info(captions, orientation='vertical')
        self.w_save_button = b
        b.save.add_callback('activated', self.save_cb)
        save_button_frame.set_widget(w)
        vbox.add_widget(save_button_frame, stretch=0)

        # Attach the scrollable area to the container we were given.
        container.set_margins(0, 0, 0, 0)
        container.set_spacing(4)
        container.add_widget(sw, stretch=1)

    def set_data_quality(self, rating, value):
        if not value:
            return
        try:
            if self.oblist_index is None:
                return
            if self.w_prog_ob.dup_all_ob.get_state():
                targets = list(self.oblist_indices)
            else:
                targets = [self.oblist_indices[self.oblist_index]]
            for index in targets:
                ob = self.oblist[index]
                ob_str = str(ob)
                self.ob_resolution[ob_str]['dq'] = rating
                self.logger.debug('ob %s dq=%d' % (ob_str, rating))
                ob.data_quality = rating
                if rating > 2:
                    ob.status = 'complete'
                elif rating > 0:
                    ob.status = 'incomplete'
                else:
                    ob.status = 'new'
        except Exception as e:
            self.logger.error('Error in set_data_quality: %s %s'
                              % (value, str(e)))

    def rate_cb(self, widget, value, rating):
        self.set_data_quality(rating, value)

    def save_cb(self, widget):
        try:
            self.save_comments()
            for ob in self.ob_resolution:
                cmt_text = self.ob_resolution[ob]['OB_Comments']
                dq = self.ob_resolution[ob]['dq']
                self.logger.debug('ob %s cmt_text %s iq %d'
                                  % (ob, cmt_text, dq))
            for index in self.oblist_indices:
                ob = self.oblist[index]
                ob_str = str(ob)
                ob.comment = self.ob_resolution[ob_str]['OB_Comments']
            for ob in self.oblist:
                self.logger.info(
                    'ob %s comment %s data_quality %s'
                    % (ob, ob.comment, ob.data_quality))
        except Exception as e:
            self.logger.error('Error in save_cb: %s' % str(e))

    def clear_cb(self, widget):
        self.logger.info('clear clicked')
        try:
            if self.oblist_index is None:
                return
            ob = self.oblist[self.oblist_indices[self.oblist_index]]
            ob_str = str(ob)
            self.w_comments.comment_entry.clear()
            for name in self.qualityButtons:
                self.quality_radios[name].set_state(False)
            self.ob_resolution[ob_str]['OB_Comments'] = ''
            self.ob_resolution[ob_str]['dq'] = 0
            ob.data_quality = 0
            ob.status = 'new'
        except Exception as e:
            self.logger.error('Error in clear_cb: %s' % str(e))

    def save_comments(self):
        if self.oblist_index is None:
            return
        current_comment = self.w_comments.comment_entry.get_text()
        if self.w_prog_ob.dup_all_ob.get_state():
            for index in self.oblist_indices:
                ob = self.oblist[index]
                self.ob_resolution[str(ob)]['OB_Comments'] = current_comment
        else:
            key = str(self.oblist[self.oblist_indices[self.oblist_index]])
            self.ob_resolution[key]['OB_Comments'] = current_comment

    def show_ob(self):
        try:
            ob = self.oblist[self.oblist_indices[self.oblist_index]]
            ob_str = str(ob)
            self.w_prog_ob.program.set_text(ob.program.proposal)
            self.w_prog_ob.ob_id.set_text(ob.id)
            resolution = self.ob_resolution[ob_str]
            self.w_comments.comment_entry.set_text(resolution['OB_Comments'])
            dq = resolution['dq']
            for name in self.qualityButtons:
                self.quality_radios[name].set_state(
                    dq == self.qualityButtonVals[name])
        except Exception as e:
            self.logger.error(str(e))

    def select_ob(self, position):
        try:
            if len(self.oblist) == 0:
                return
            self.save_comments()
            if position == 'first':
                self.oblist_index = 0
                self.w_slider.ob_list_index.set_value(self.oblist_index)
            elif position == 'prev':
                if self.oblist_index > 0:
                    self.oblist_index -= 1
                    self.w_slider.ob_list_index.set_value(self.oblist_index)
            elif position == 'next':
                if self.oblist_index < len(self.oblist_indices) - 1:
                    self.oblist_index += 1
                    self.w_slider.ob_list_index.set_value(self.oblist_index)
            elif position == 'last':
                self.oblist_index = len(self.oblist_indices) - 1
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
        self.logger.debug('resolve_obs called oblist is %s len is %d'
                          % (oblist, len(oblist)))
        self.oblist = oblist
        self.ob_resolution = {}
        self.oblist_indices = []
        if len(oblist) > 0:
            # Build a list of the indices of OB's that are not
            # "derived", i.e., not "Filter Change", "Long slew",
            # "Delay for"
            for i, ob in enumerate(self.oblist):
                if ob.derived is None:
                    self.oblist_indices.append(i)
                    self.ob_resolution[str(ob)] = {}
                    self.ob_resolution[str(ob)]['OB_Comments'] = ob.comment
                    self.ob_resolution[str(ob)]['dq'] = ob.data_quality

            self.logger.debug('oblist_indices %s' % self.oblist_indices)
            self.oblist_index = 0
            self.w_slider.ob_list_index.set_limits(
                0, len(self.oblist_indices) - 1)
            self.w_slider.ob_list_index.set_value(self.oblist_index)
            self.show_ob()
        else:
            self.w_prog_ob.program.set_text('N/A')
            self.w_prog_ob.ob_id.set_text('N/A')
