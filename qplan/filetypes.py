#
# filetypes.py -- CSV file interfaces
#
# R. Kackley
# E. Jeschke
#
import os
import csv
from io import BytesIO, StringIO
import datetime
import re

import pandas as pd
from pandas.plotting import register_matplotlib_converters

from ginga.misc import Bunch

from . import entity
try:
    from .cfg import HSC_cfg
    have_HSC_cfg = True
except (ImportError, FileNotFoundError) as e:
    have_HSC_cfg = False
from qplan.util.site import site_subaru
import qplan.util.calcpos
from .common import hsc_extra_overhead_factor

# In moon_states, the dict keys are the allowable the Phase 1 Moon
# illumination names. The dict values are the list of acceptable Moon
# values in the envcfg sheet.
moon_states = {'dark': ('dark', 'gray', 'dark+gray'),
               'gray': ('gray', 'dark+gray'),
               'dark/gray': ('gray', 'dark+gray'),
               'dark+gray': ('gray', 'dark+gray')}
moon_states_upper = [state.upper() for state in moon_states.keys()]
moon_sep_dist_warn = 30.0

class FileNotFoundError(Exception):
    pass
class UnknownFileFormatError(Exception):
    pass

class QueueFile(object):

    # Default format parameters for reading/writing CSV files.
    fmtparams = {'delimiter':',', 'quotechar':'"', 'quoting': csv.QUOTE_MINIMAL}
    # The order of the file extensions in all_ext defines the
    # preferred order of searching for files, i.e., we search for
    # *.xlsx files first, and, if not found, proceed on to the next
    # extension in the list.
    excel_ext = ['xlsx', 'xls']
    all_ext = excel_ext + ['csv']

    def __init__(self, input_dir, file_prefix, logger, file_ext=None,
                 **parse_kwdargs):
        self.input_dir = input_dir
        self.logger = logger
        self.queue_file = None
        self.columnNames = []
        self.rows = []
        self.parse_kwdargs = parse_kwdargs

        self.file_prefix = file_prefix
        self.file_ext = file_ext
        self.filepath = None
        self.stringio = {}
        self.excel_converters = None

    def find_filepath(self):
        self.filepath = None
        # If the file extension is specified, use it to find the
        # file. Otherwise, use the file extensions in the all_ext list.
        if self.file_ext:
            filename = '.'.join([self.file_prefix, self.file_ext])
            filepath = os.path.join(self.input_dir, filename)
            if os.path.exists(filepath):
                self.filepath = filepath
            else:
                raise FileNotFoundError('File %s not found' % filepath)
        else:
            for file_ext in self.all_ext:
                filename = '.'.join([self.file_prefix, file_ext])
                filepath = os.path.join(self.input_dir, filename)
                if os.path.exists(filepath):
                    self.filepath = filepath
                    self.file_ext = file_ext
                    break

        if not self.filepath:
            raise FileNotFoundError("File with prefix '%s' and extension %s not found" % (self.file_prefix, self.all_ext))

    def read_csv_file(self):
        if self.filepath:
            self.logger.info('Reading file %s' % self.filepath)
            with open(self.filepath, 'r') as f:
                buf = StringIO(f.read())
                self.stringio[self.file_prefix] = buf
        else:
            raise IOError('File path not defined for file prefix %s' % self.file_prefix)

    def read_excel_file(self):
        self.df = {}
        if self.filepath:
            self.logger.info('Reading file %s' % self.filepath)
            self.file_obj.seek(0)
            with pd.ExcelFile(self.file_obj) as datasrc:
                for name in datasrc.sheet_names:
                    # We use the ExcelFile.parse "converters" argument
                    # only for sheets that have column(s) where we
                    # expect integer values. The converter helps us
                    # when the sheet has blank rows and keeps the
                    # Pandas DataFrame from converting the column from
                    # integers to floats.
                    try:
                        excel_converters = self.cfg[name].excel_converters
                    except (KeyError, AttributeError):
                        excel_converters = None
                    self.df[name] = datasrc.parse(name, converters=excel_converters)
                    buf = StringIO()
                    self.stringio[name] = buf
                    self.df[name].to_csv(self.stringio[name], index=False)
                    self.stringio[name].seek(0)
        else:
            raise IOError('File path not defined for file prefix %s' % self.file_prefix)

    def is_excel_file(self):
        if self.file_ext in self.excel_ext:
            return True
        else:
            return False

    def process_input(self):
        # Read and save the first line, which should have the column
        # titles.
        self.stringio[self.name].seek(0)
        self.queue_file = self.stringio[self.name]
        reader = csv.reader(self.queue_file, **self.fmtparams)
        self.columnNames = next(reader)

        # Read the rest of the file and put the contents into a list
        # data structure (i.e., the "rows" attribute). The column
        # titles will be the dictionary keys.
        reader = csv.DictReader(self.queue_file.getvalue().splitlines(),
                                **self.fmtparams)
        for row in reader:
            self.rows.append(row)

        self.parse_input()
        # We are done with the BytesIO object, so close it.
        self.queue_file.close()

    def write_output(self, new_filepath=None):
        # Write the data to the specified output file. If a
        # new_filepath is supplied, use it. Otherwise, use the
        # existing filepath.
        if new_filepath:
            self.filepath = new_filepath

        # Open the file for writing.
        with open(self.filepath, 'wb') as f:
            # Write the column titles first
            writer = csv.writer(f, **self.fmtparams)
            writer.writerow(self.columnNames)

            # Write the rest of the file from the "rows" attribute,
            # which stores the data as a list of dictionaries.
            writer = csv.DictWriter(f, self.columnNames, **self.fmtparams)
            for row in self.rows:
                writer.writerow(row)

    def parse_input(self):
        raise NotImplementedError("subclass should override this")

    def update(self, row, colHeader, value, parse_flag):
        # User has changed a value in the table, so update our "rows"
        # attribute, recreate the BytesIO object, and parse the input
        # again.
        self.logger.debug('QueueFile.update row %d colHeader %s value %s' % (row, colHeader, value))
        self.rows[row][colHeader] = value

        # Use the CSV "writer" classes to create a new version of the
        # BytesIO object from our "rows" attribute.
        if parse_flag:
            self.parse()

    def parse(self):
        # Create a buffer object and write our columnNames
        # and rows attributes into that object. This gives us an
        # object that looks like a disk file so we can parse the data.
        self.queue_file = StringIO()
        writer = csv.writer(self.queue_file, **self.fmtparams)
        writer.writerow(self.columnNames)
        writer = csv.DictWriter(self.queue_file, self.columnNames, **self.fmtparams)
        for row in self.rows:
            writer.writerow(row)

        # Parse the input data from the buffer
        try:
            self.parse_input()

        except Exception as e:
            self.logger.error("Error reparsing input: %s" % (str(e)))

        # We are done with the buffer, so close it.
        self.queue_file.close()

    def parse_row(self, row, column_names, column_map):
        """
        Parse a row of values (tup or list) into a record that can
        be accessed by attribute or map key.
        column_names is a list of column names matching the sequence of
        values in a row.  column_map is a dictionary mapping column names
        to the names that should be assigned in the resulting record.
        """
        rec = Bunch.Bunch()
        for i in range(len(row)):
            if i >= len(column_names):
                break
            # mangle header to get column->attribute mapping key
            colname = column_names[i]
            key = colname.strip().lower().replace(' ', '_').replace('-', '_')
            # get attr key
            if not key in column_map:
                #self.logger.warning("No column->record map entry for column '%s' (%s); skipping..." % (colname, key))
                continue
            attrkey = column_map[key]
            rec[attrkey] = row[i].strip()
        return rec

    def validate_column_names(self, progFile):
        # Check to make sure that the supplied sheet has the required
        # column names in the first row. Also, check for duplicate
        # column names.

        begin_error_count = progFile.error_count

        # First, get the column names from the first row.
        self.stringio[self.name].seek(0)
        reader = csv.reader(self.stringio[self.name], **self.fmtparams)
        column_names = next(reader)

        # Iterate through the list of required columns to make sure
        # they are all there.
        for col_name, info in self.columnInfo.items():
            if info['required']:
                if info['iname'] in column_names:
                    self.logger.debug('Required column name %s found in sheet %s' % (info['iname'], self.name))
                else:
                    msg = 'Required column %s not found in sheet %s' % (info['iname'], self.name)
                    progFile.logger.error(msg)
                    progFile.errors[self.name].append([0, [info['iname']], msg])
                    progFile.error_count += 1

            else:
                if info['iname'] in column_names:
                    self.logger.debug('Optional column name %s found in sheet %s' % (info['iname'], self.name))

            # Warn the user if there is a column with a name that
            # starts with one of the expected names, but then has
            # appended to the name a ".1", ".2", etc. This means
            # that there was a duplicate column name in the
            # spreadsheet and Pandas appended a sequence number to
            # make the subsequent columns have unique names.
            pattern = info['iname'] + r'\.\d+'
            dup_list = []
            for cname in column_names:
                if re.match(pattern, cname):
                    dup_list.append(cname)

            dup_count = len(dup_list)
            if dup_count > 0:
                msg = 'Warning: %d duplicate %s column(s) found in sheet %s' % (dup_count, info['iname'], self.name)
                progFile.logger.warning(msg)
                progFile.warnings[self.name].append([0, dup_list, msg])
                progFile.warn_count += 1

        return progFile.error_count - begin_error_count

    def checkCodesUnique(self, progFile):
        # Check to see if there are any duplicate values in the Code
        # column.

        begin_warn_count = progFile.warn_count

        # First, get the column names to see if there is a Code
        # column.
        self.stringio[self.name].seek(0)
        reader = csv.reader(self.stringio[self.name], **self.fmtparams)
        column_names = next(reader)

        # If there is a Code column, check for duplicate codes.
        if 'Code' in column_names:
            codes = {}
            for i, row in enumerate(reader):
                rec = self.parse_row(row, column_names, self.column_map)
                row_num = i + 1
                if self.ignoreRow(row, rec):
                    progFile.logger.debug('On Sheet %s, ignore Line %d with contents %s' % (self.name, row_num, row))
                else:
                    if len(rec.code) > 0 and rec.code in codes:
                        msg = "Error while checking line %d, column Code of sheet %s: Duplicate code value identified: %s" % (row_num, self.name, rec.code)
                        progFile.logger.error(msg)
                        progFile.errors[self.name].append([row_num, [self.columnInfo['code']['iname']], msg])
                        progFile.error_count += 1
                    else:
                        codes[rec.code] = True

        return progFile.warn_count - begin_warn_count

    def ignoreRow(self, row, rec):
        # If all columns, except possibly the Comment column and the
        # ones that have columnInfo['prefilled'] set to True, are
        # blank, or if the first column has the word "comment" in it,
        # then this row is considered a blank or a comment row and can
        # be ignored. Also, for the OBListFile, if the content of the
        # first column starts with "#", then the row can be ignored.
        first_col_content = row[0].strip()
        if first_col_content.lower() == 'comment' or \
               (isinstance(self, OBListFile) and len(first_col_content) > 0 and first_col_content[0] == '#'):
            return True
        # If this is the "targets" or "inscfg" sheet, and the first
        # column has the string "default" in it, then ignore the row.
        if self.name in ('targets', 'inscfg') and first_col_content.lower() == 'default':
            return True
        for i, col_name in enumerate(self.column_map):
            if col_name == 'comment':
                continue
            if (col_name in self.columnInfo and
                self.columnInfo[col_name]['prefilled']):
                continue

            try:
                if len(rec[self.column_map[col_name]]) > 0:
                    return False
            except KeyError as e:
                if (col_name in self.columnInfo and
                    self.columnInfo[col_name]['required']):
                    self.logger.error('Unexpected error in ignoreRow while checking column %s: %s' % (col_name, str(e)))
                else:
                    pass
        return True

    def validate_datatypes(self, progFile):
        # Validate the data in the sheet by checking the datatypes of
        # the values.

        begin_error_count = progFile.error_count

        # First, get the column names from the first row.
        self.stringio[self.name].seek(0)
        reader = csv.reader(self.stringio[self.name], **self.fmtparams)
        column_names = next(reader)

        for i, row in enumerate(reader):
            progFile.logger.debug('Sheet %s Line %d Row is %s' % (self.name, i+1, row))
            row_num = i + 1
            rec = self.parse_row(row, column_names, self.column_map)

            # Ignore comment rows
            if self.ignoreRow(row, rec):
                progFile.logger.debug('On Sheet %s, ignore Line %d with contents %s' % (self.name, row_num, row))

            else:
                # Iterate through all the columns and check dataypes
                for col_name, info in self.columnInfo.items():
                    rec_name = self.column_map[col_name]
                    try:
                        str_val = rec[rec_name]
                    except KeyError as e:
                        continue

                    # See if we can coerce the string value into the
                    # desired datatype.
                    try:
                        val = info['type'](str_val)
                    except ValueError as e:
                        msg = 'Error evaluating line %d, column %s of sheet %s: '% (row_num, info['iname'], self.name)
                        if len(str_val) > 0:
                            msg += "Non-numeric value, '%s', " % str_val
                        else:
                            msg += 'Blank value '
                        msg += 'found where a numeric value was expected'
                        progFile.logger.error(msg)
                        progFile.errors[self.name].append([row_num, [info['iname']], msg])
                        progFile.error_count += 1
                        continue

        return progFile.error_count - begin_error_count

    def validate_data(self, progFile, propname=None):
        # Validate the data in the sheet by checking any specified
        # constraints.

        begin_error_count = progFile.error_count

        # First, get the column names from the first row.
        self.stringio[self.name].seek(0)
        reader = csv.reader(self.stringio[self.name], **self.fmtparams)
        column_names = next(reader)

        for i, row in enumerate(reader):
            progFile.logger.debug('Sheet %s Line %d Row is %s' % (self.name, i+1, row))
            row_num = i + 1
            rec = self.parse_row(row, column_names, self.column_map)

            # Ignore comment rows
            if self.ignoreRow(row, rec):
                progFile.logger.debug('On Sheet %s, ignore Line %d with contents %s' % (self.name, row_num, row))

            else:
                # Iterate through all the columns and check
                # constraints, if any.
                for col_name, info in self.columnInfo.items():
                    rec_name = self.column_map[col_name]
                    try:
                        str_val = rec[rec_name]
                    except KeyError as e:
                        continue

                    # We have already checked the datatypes in
                    # validate_datatypes, so the next line should not
                    # result in any errors.
                    val = info['type'](str_val)

                    # If there is a constraint, check the value to see
                    # if it meets the constraint requirement.
                    if info['constraint']:
                        # Try to convert value to upper case. If we
                        # get an AttributeError, that means that val
                        # is not a string, so ignore the exception.
                        try:
                            val = val.upper()
                        except AttributeError:
                            pass

                        if isinstance(info['constraint'], str):
                            l = lambda value: eval(info['constraint'])
                            if l(val):
                                self.logger.debug('Line %d, column %s of sheet %s: %s meets the constraint of %s' % (row_num, info['iname'], self.name, val, info['constraint']))
                            else:
                                msg = "Error while checking line %d, column %s of sheet %s: '%s' does not meet the constraint of %s" % (row_num, info['iname'], self.name, val, info['constraint'])
                                progFile.logger.error(msg)
                                progFile.errors[self.name].append([row_num, [info['iname']], msg])
                                progFile.error_count += 1
                        else:
                            l = info['constraint']
                            l(val, rec, row_num, col_name, progFile)

        return progFile.error_count - begin_error_count

    def checkForOrphanCodes(self, progFile, ob_col_name_list):
        # Check to see if the codes supplied in the sheet appears in
        # the ob sheet. If not, report a warning.

        # Iterate through all the rows in the sheet
        for i, row in enumerate(self.rows):
            row_num = i + 1
            code = row['Code']
            # Ignore code values that are blank
            if len(code) > 0:
                # Ignore rows that have the "Code" value set to the
                # string "comment" or, on "targets" and "inscfg"
                # sheets, "Code" set to "default".
                if code.lower() == 'comment' or (self.name in ('targets', 'inscfg') and code.lower() == 'default'):
                    progFile.logger.debug('On Sheet %s, ignore Line %d with contents %s' % (self.name, row_num, row))
                else:
                    # Check to see that the specified code appears in
                    # the ob sheet.
                    found = False
                    for ob_row in progFile.cfg['ob'].rows:
                        codes = []
                        # Ignore any column names in ob_col_name_list
                        # that don't exist in the "ob" sheet.
                        for n in ob_col_name_list:
                            try:
                                codes.append(ob_row[n])
                            except KeyError as e:
                                pass
                        if code in codes:
                            found = True
                            break
                    if found:
                        progFile.logger.debug('Line %d of sheet %s: Code %s was found in ob sheet' % (row_num, self.name, row['Code']))
                    else:
                        msg = 'Warning while checking line %d of sheet %s: Code %s was not found in ob sheet' % (row_num, self.name, row['Code'])
                        progFile.logger.warning(msg)
                        progFile.warnings[self.name].append([row_num, ['Code',], msg])
                        progFile.warn_count += 1

class ScheduleFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        # schedule_info is the list of tuples that will be used by the
        # observing block scheduling functions.
        self.name = 'schedule'
        self.schedule_info = []
        self.column_map = {
            'date': 'date',
            'start_time': 'starttime',
            'end_time': 'stoptime',
            'categories': 'categories',
            'instruments': 'instruments',
            'filters': 'filters',
            'transparency': 'transparency',
            'avg_seeing': 'seeing',
            'dome': 'dome',
            'cur_filter': 'cur_filter',
            'cur_az': 'cur_az',
            'cur_el': 'cur_el',
            'cur_rot': 'cur_rot',
            'skip': 'skip',
            'note': 'note',
            }
        super(ScheduleFile, self).__init__(input_dir, 'schedule', logger, file_ext)
        self.find_filepath()
        if self.file_ext == 'csv':
            self.read_csv_file()
        elif self.is_excel_file():
            with open(self.filepath, 'rb') as excel_file:
                self.file_obj = BytesIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('Schedule file format %s is unknown' % self.file_ext)
        self.process_input()

    def parse_input(self):
        """
        Parse the observing schedule from the input file.
        """
        self.queue_file.seek(0)
        self.schedule_info = []
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                self.logger.debug('ScheduleFile.parse_input rec %s' % (rec))

            except Exception as e:
                raise ValueError("Error reading line %d of schedule: %s" % (
                    lineNum, str(e)))

            # "date" column might be in "YYYY-MM-DD" or in "YYYY-MM-DD
            # HH:MM:SS" format. Parse input value and convert to
            # "YYYY-MM-DD" string.
            rec.date = site_subaru.get_date(rec.date).strftime('%Y-%m-%d')

            filters = [s.strip() for s in rec.filters.lower().split(',')]
            instruments = [s.strip()
                           for s in rec.instruments.upper().split(',')]
            seeing = float(rec.seeing)
            categories = rec.categories.replace(' ', '').lower().split(',')
            transparency = float(rec.transparency)
            dome = rec.dome.lower()

            cur_filter = rec.get('cur_filter', None)
            if cur_filter is not None:
                cur_filter = cur_filter.lower()
            cur_az = rec.get('cur_az', None)
            if cur_az is not None:
                cur_az = float(cur_az)
            cur_el = rec.get('cur_el', None)
            if cur_el is not None:
                cur_el = float(cur_el)
            cur_rot = rec.get('cur_rot', None)
            if cur_rot is not None:
                cur_rot = float(cur_rot)
            else:
                cur_rot = 0.0

            skip = False
            if rec.has_key('skip'):
                skip = rec.skip.strip() != ''

            # data record of current conditions
            # All OBs for this schedule slot should end up pointing to this
            # static record
            data = Bunch.Bunch(filters=filters, cur_filter=cur_filter,
                               cur_az=cur_az, cur_el=cur_el, cur_rot=cur_rot,
                               seeing=seeing, transparency=transparency,
                               dome=dome, categories=categories,
                               instruments=instruments)

            rec2 = Bunch.Bunch(date=rec.date, starttime=rec.starttime,
                               stoptime=rec.stoptime,
                               #categories=categories,
                               skip=skip,
                               note=rec.note,
                               data=data)
            self.schedule_info.append(rec2)

class ProgramsFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        # programs_info is the dictionary of Program objects that will
        # be used by the observing block scheduling functions.
        self.name = 'programs'
        self.programs_info = {}
        self.column_map = {
            'proposal': 'proposal',
            'pi_name': 'pi_name',
            'propid': 'propid',
            'rank': 'rank',
            'category': 'category',
            'instruments': 'instruments',
            'grade': 'grade',
            'qcp': 'qc_priority',
            'hours': 'hours',
            'partner': 'partner',
            'skip': 'skip',
            }
        super(ProgramsFile, self).__init__(input_dir, 'programs', logger,
                                           file_ext)
        self.find_filepath()
        if self.file_ext == 'csv':
            self.read_csv_file()
        elif self.is_excel_file():
            with open(self.filepath, 'rb') as excel_file:
                self.file_obj = BytesIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('Programs file format %s is unknown' % self.file_ext)
        self.process_input()

    def parse_input(self):
        """
        Parse the programs from the input file.
        """
        self.queue_file.seek(0)
        old_info = self.programs_info
        self.programs_info = {}
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)

                skip = rec.skip.strip() != ''

                key = rec.proposal.upper()
                pgm = entity.Program(key, propid=rec.propid,
                                     pi=rec.pi_name,
                                     rank=float(rec.rank),
                                     qc_priority=float(rec.get('qc_priority', 0.0)),
                                     grade=rec.grade.upper(),
                                     partner=rec.partner,
                                     category=rec.category,
                                     skip=skip,
                                     instruments=rec.instruments.upper().split(','),
                                     hours=float(rec.hours))

                # update existing old program record if it exists
                # since OBs may be pointing to it
                if key in old_info:
                    new_pgm = pgm
                    pgm = old_info[key]
                    pgm.__dict__.update(new_pgm.__dict__)

                self.programs_info[key] = pgm

            except Exception as e:
                raise ValueError("Error reading line %d of programs: %s" % (
                    lineNum, str(e)))

    def update_table(self, tbl_dct, parse_flag=False):
        """Update items in the internal table representation (self.rows).
        """

        for row_key, col_dct in tbl_dct.items():

            row_key = row_key.upper()
            # locate row index for this row_key
            # TODO: make more efficient!
            found = False
            for row_idx in range(0, len(self.rows)):
                if self.rows[row_idx]['proposal'].upper() == row_key:
                    found = True
                    break

            if not found:
                raise ValueError(f"Can't find entry for row_key={row_key}")

            for col_key, col_val in col_dct.items():
                # locate column header for this col_key
                # TODO: make more efficient!
                found = False
                for col_hdr, ent_field in self.column_map.items():
                    if ent_field == col_key:
                        found = True
                        break

                if not found:
                    raise ValueError(f"Can't find entry for col_key={col_key}")

                # update the cell in the table representation
                self.rows[row_idx][col_hdr] = col_val

        if parse_flag:
            self.parse()


class WeightsFile(QueueFile):

    def __init__(self, input_dir, logger, file_ext=None):

        self.name = 'weights'
        self.weights = Bunch.Bunch()
        self.column_map = {
            'slew': 'w_slew',
            'rotator': 'w_rotator',
            'delay': 'w_delay',
            'filter': 'w_filterchange',
            'rank': 'w_rank',
            'priority': 'w_priority',
            'qcp': 'w_qcp',
            }
        super(WeightsFile, self).__init__(input_dir, 'weights', logger, file_ext)
        self.find_filepath()
        if self.file_ext == 'csv':
            self.read_csv_file()
        elif self.is_excel_file():
            with open(self.filepath, 'rb') as excel_file:
                self.file_obj = BytesIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('Weights file format %s is unknown' % self.file_ext)
        self.process_input()

    def parse_input(self):
        """
        Parse the weights from the input file.
        """
        self.queue_file.seek(0)
        self.weights = Bunch.Bunch()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                ## if rec.skip.strip() != '':
                ##     continue

                # remember the last one read
                zipped = rec.items()
                keys, vals = zip(*zipped)
                self.weights = Bunch.Bunch(zip(keys, map(float, vals)))

            except Exception as e:
                raise ValueError("Error reading line %d of weights: %s" % (
                    lineNum, str(e)))

class ProposalFile(QueueFile):

    propID_re = re.compile(r'^S\d{2}[AB]-[-\w]{1,10}$')

    def __init__(self, input_dir, logger, file_ext=None):

        self.name = 'proposal'
        self.proposal_info = Bunch.Bunch()
        self.column_map = {
            'prop_id': 'prop_id',
            'ph1_seeing': 'ph1_seeing',
            'ph1_transparency': 'ph1_transparency',
            'allocated_time': 'allocated_time',
            'ph1_moon': 'ph1_moon',
            'maximum_ob_length': 'maximum_ob_length',
            }
        self.columnInfo = {
            'prop_id':          {'iname': 'Prop ID',          'type': str,   'constraint': self.checkPropID,                       'prefilled': False, 'required': True},
            'ph1_seeing':       {'iname': 'Ph1 Seeing',       'type': float, 'constraint': "value > 0.0",                          'prefilled': False, 'required': True},
            'ph1_transparency': {'iname': 'Ph1 Transparency', 'type': float, 'constraint': "value >= 0.0 and value <= 1.0",        'prefilled': False, 'required': True},
            'ph1_moon':         {'iname': 'Ph1 Moon',         'type': str,   'constraint': "value in %s" % str(moon_states_upper), 'prefilled': False, 'required': True},
            'allocated_time':   {'iname': 'Allocated Time',   'type': float, 'constraint': "value >= 0.0",                         'prefilled': False, 'required': True},
            'maximum_ob_length': {'iname': 'Maximum OB Length', 'type': float, 'constraint': "value >= 0.0",                       'prefilled': False, 'required': False},
            }
        super(ProposalFile, self).__init__(input_dir, 'proposal', logger, file_ext)

    def parse_input(self):
        """
        Read the proposal information from a CSV file.
        """
        self.queue_file.seek(0)
        self.proposal_info = Bunch.Bunch()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                ## if rec.skip.strip() != '':
                ##     continue

                # remember the last one read
                self.proposal_info = Bunch.Bunch(rec.items())

            except Exception as e:
                raise ValueError("Error reading line %d of proposal: %s" % (
                    lineNum, str(e)))

    def checkPropID(self, val, rec, row_num, col_name, progFile):
        iname = self.columnInfo[col_name]['iname']
        valid = False
        if len(val) > 0:
            if self.propID_re.match(val):
                progFile.logger.debug('Line %d, column %s of sheet %s: %s %s is ok' % (row_num, iname, self.name, iname, val))
                valid = True
            else:
                valid = False
        else:
            valid = False
        if not valid:
            msg = "Error while checking line %d, column %s of sheet %s: %s '%s' is not a valid proposal ID" % (row_num, iname, self.name, iname, val)
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [iname], msg])
            progFile.error_count += 1
        return valid

class TelCfgFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        self.name = 'telcfg'
        self.tel_cfgs = {}
        self.column_map = {
            'code': 'code',
            'foci': 'focus',
            'dome': 'dome',
            'comment': 'comment',
            }
        self.foci = "('P-OPT2',)"
        self.dome_states = "('Open', 'Closed')".upper()
        self.columnInfo = {
            'code':         {'iname': 'Code', 'type': str, 'constraint': "len(value) > 0",                 'prefilled': False, 'required': True},
            'foci':         {'iname': 'Foci', 'type': str, 'constraint': "value in %s" % self.foci,        'prefilled': False, 'required': True},
            'dome':         {'iname': 'Dome', 'type': str, 'constraint': "value in %s" % self.dome_states, 'prefilled': False, 'required': True},
            }
        super(TelCfgFile, self).__init__(input_dir, 'telcfg', logger, file_ext)

    def parse_input(self):
        """
        Read all telescope configurations from a CSV file.
        """
        self.queue_file.seek(0)
        old_cfgs = self.tel_cfgs
        self.tel_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                telcfg = entity.TelescopeConfiguration()
                code = telcfg.import_record(rec)

                # update existing old record if it exists
                # since OBs may be pointing to it
                if code in old_cfgs:
                    new_cfg = telcfg
                    telcfg = old_cfgs[code]
                    telcfg.__dict__.update(new_cfg.__dict__)

                self.tel_cfgs[code] = telcfg

            except Exception as e:
                raise ValueError("Error reading line %d of telcfgs from file %s: %s" % (
                    lineNum, self.filepath, str(e)))


class EnvCfgFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        self.name = 'envcfg'
        self.env_cfgs = {}
        self.column_map = {
            'code': 'code',
            'seeing': 'seeing',
            'airmass': 'airmass',
            'moon': 'moon',
            'moon_sep': 'moon_sep',
            #'sky': 'sky',
            'transparency': 'transparency',
            'lower_time_limit': 'lower_time_limit',
            'upper_time_limit': 'upper_time_limit',
            'comment': 'comment',
            }
        self.columnInfo = {
            'code':         {'iname': 'Code',         'type': str,   'constraint': "len(value) > 0", 'prefilled': False, 'required': True},
            'seeing':       {'iname': 'Seeing',       'type': float, 'constraint': self.seeing_check, 'prefilled': False, 'required': True},
            'airmass':      {'iname': 'Airmass',      'type': float, 'constraint': "value >= 1.0",   'prefilled': False, 'required': False},
            'moon':         {'iname': 'Moon',         'type': str,   'constraint': self.moon_check,  'prefilled': False, 'required': True},
            'moon_sep':     {'iname': 'Moon Sep',     'type': float, 'constraint': self.moon_sep_check,  'prefilled': False, 'required': True},
            'transparency': {'iname': 'Transparency', 'type': float, 'constraint': self.transparency_check,   'prefilled': False, 'required': True},
            'lower_time_limit': {'iname': 'Lower Time Limit', 'type': str, 'constraint': self.lowerTimeLimitCheck, 'prefilled': False, 'required': False},
            'upper_time_limit': {'iname': 'Upper Time Limit', 'type': str, 'constraint': self.upperTimeLimitCheck, 'prefilled': False, 'required': False},
            }
        self.default_timezone = entity.EnvironmentConfiguration.default_timezone
        self.seeing_choices = [0.8, 1.0, 1.3, 1.6, 100.0]
        self.transparency_choices = [0.7, 0.4, 0.1, 0.0]
        # Seeing and transparency values will be filled in by the
        # update_constraints method
        self.seeing_from_ph1 = None
        self.transparency_from_ph1 = None
        # semester value will be set by validate_data method
        self.semester = None
        # Default airmass if armass column is not found - use airmass
        # at 30 deg elevation
        self.default_airmass = qplan.util.calcpos.alt2airmass(30.0)
        super(EnvCfgFile, self).__init__(input_dir, 'envcfg', logger, file_ext)

    def validate_data(self, progFile, propname):
        prop_split = propname.split('-')
        self.semester = prop_split[0]
        return super(EnvCfgFile, self).validate_data(progFile)

    def dateTimeCheck(self, val, rec, row_num, col_name, progFile):
        iname = self.columnInfo[col_name]['iname']
        try:
            pdt = entity.parse_date_time(val, self.default_timezone)
            progFile.logger.debug("Line %d, column %s of sheet %s: %s '%s' is ok" % (row_num, col_name, self.name, iname, val))
        except (ValueError, OverflowError) as e:
            msg = "Error while checking line %d, column %s of sheet %s: %s value '%s' is not valid" % (row_num, iname, self.name, iname, val)
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [iname], msg])
            progFile.error_count += 1

    def lowerTimeLimitCheck(self, val, rec, row_num, col_name, progFile):
        self.dateTimeCheck(val, rec, row_num, col_name, progFile)

    def upperTimeLimitCheck (self, val, rec, row_num, col_name, progFile):
        # Checking the upper time limit means checking the upper time
        # limit itself and also doing few checks on the upper and
        # lower time limits together. First, check to see if we can
        # parse the upper time limit. If net, return immediately
        # because we can't do anything else.
        err_count = progFile.error_count
        self.dateTimeCheck(val, rec, row_num, col_name, progFile)
        if progFile.error_count > err_count:
            return

        iname = self.columnInfo[col_name]['iname']
        # Now check the lower time limit and upper time limit
        # together. First, make sure that we can parse the lower time
        # limit. If net, return immediately because we can't do
        # anything else.
        try:
            lower_time_limit = entity.parse_date_time(rec.lower_time_limit,
                                                      self.default_timezone)
        except (ValueError, OverflowError) as e:
            return
        # Check the lower and upper time limits together. We want to
        # make sure that the upper time limit is greater than the
        # lower time limit. Also, we want to make sure that, if one
        # limit value was supplied, then there must also be a value
        # for the other limit.
        upper_time_limit = entity.parse_date_time(val,
                                                  self.default_timezone)
        if lower_time_limit is not None or upper_time_limit is not None:
            try:
                if upper_time_limit > lower_time_limit:
                    progFile.logger.debug('Line %d, column %s of sheet %s: %s %s is greater than Lower Time Limit %s and is ok' % (row_num, col_name, self.name, iname, val, rec.lower_time_limit))
                else:
                    msg = "Error while checking line %d, column %s of sheet %s: %s value %s must be greater than Lower Time Limit value %s" % (row_num, iname, self.name, iname, val, rec.lower_time_limit)
                    progFile.logger.error(msg)
                    progFile.errors[self.name].append([row_num, [iname], msg])
                    progFile.error_count += 1
            except TypeError:
                if lower_time_limit is not None and upper_time_limit is None:
                    msg = "Error while checking line %d, column %s of sheet %s: Lower Time Limit value is %s - %s value must not be blank" % (row_num, iname, self.name, rec.lower_time_limit, iname)
                    progFile.logger.error(msg)
                    progFile.errors[self.name].append([row_num, [iname], msg])
                    progFile.error_count += 1
                if lower_time_limit is None and upper_time_limit is not None:
                    msg = "Error while checking line %d, column %s of sheet %s: %s value is %s - Lower Time Limit value must not be blank" % (row_num, iname, self.name, iname, val)
                    progFile.logger.error(msg)
                    progFile.errors[self.name].append([row_num, [iname], msg])
                    progFile.error_count += 1

    def parse_input(self):
        """
        Read all environment configurations from a CSV file.
        """
        self.queue_file.seek(0)
        old_cfgs = self.env_cfgs
        self.env_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)

                # Starting with S21A, the airmass column has been
                # removed from the envcfg sheet. If we didn't find the
                # airmass column, set airmass to the default value.
                if 'airmass' in rec:
                    self.logger.info('Using supplied airmass constraint of {}'.format(rec['airmass']))
                else:
                    rec['airmass'] = self.default_airmass
                    self.logger.info('Setting airmass constraint to default value {}'.format(rec['airmass']))

                envcfg = entity.EnvironmentConfiguration()
                code = envcfg.import_record(rec)

                # update existing old record if it exists
                # since OBs may be pointing to it
                if code in old_cfgs:
                    new_cfg = envcfg
                    envcfg = old_cfgs[code]
                    envcfg.__dict__.update(new_cfg.__dict__)

                self.env_cfgs[code] = envcfg

            except Exception as e:
                raise ValueError("Error reading line %d of envcfg from file %s: %s" % (
                    lineNum, self.filepath, str(e)))

    def update_constraints(self, proposal_info):
        self.seeing_from_ph1 =  float(proposal_info['ph1_seeing'])
        self.transparency_from_ph1 =  float(proposal_info['ph1_transparency'])

    def seeing_check(self, val, rec, row_num, col_name, progFile):
        iname = self.columnInfo[col_name]['iname']
        if self.semester < 'S19B':
            if val >= self.seeing_from_ph1:
                progFile.logger.info('Line %d, column %s of sheet %s: %s value %s is greater than or equal to %s and is ok' % (row_num, col_name, self.name, iname, val, self.seeing_from_ph1))
            else:
                msg = "Error while checking line %d, column %s of sheet %s: %s value %s must be greater than or equal to %s (Seeing from Phase 1)" % (row_num, iname, self.name, iname, val, self.seeing_from_ph1)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([row_num, [iname], msg])
                progFile.error_count += 1
        else:
            if val in self.seeing_choices and val >= self.seeing_from_ph1:
                progFile.logger.info('Line %d, column %s of sheet %s: %s value %s is in %s and is greater than or equal to %s and is ok' % (row_num, col_name, self.name, iname, val, self.seeing_choices, self.seeing_from_ph1))
            elif val not in self.seeing_choices and val >= self.seeing_from_ph1:
                msg = "Warning while checking line %d, column %s of sheet %s: %s value %s should be one of %s. %s value %s is greater than or equal to %s and is ok" % (row_num, iname, self.name, iname, val, self.seeing_choices, iname, val, self.seeing_from_ph1)
                progFile.logger.warning(msg)
                progFile.warnings[self.name].append([row_num, [iname], msg])
                progFile.warn_count += 1

            elif val in self.seeing_choices and val < self.seeing_from_ph1:
                msg = "Error while checking line %d, column %s of sheet %s: %s value %s is in %s. However, %s value %s must be greater than or equal to %s (Seeing from Phase 1)" % (row_num, iname, self.name, iname, val, self.seeing_choices, iname, val, self.seeing_from_ph1)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([row_num, [iname], msg])
                progFile.error_count += 1

            elif val not in self.seeing_choices and val < self.seeing_from_ph1:
                msg = "Error while checking line %d, column %s of sheet %s: %s value %s should be one of %s. Also, %s value %s must be greater than or equal to %s (Seeing from Phase 1)" % (row_num, iname, self.name, iname, val, self.seeing_choices, iname, val, self.seeing_from_ph1)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([row_num, [iname], msg])
                progFile.error_count += 1

    def transparency_check(self, val, rec, row_num, col_name, progFile):
        iname = self.columnInfo[col_name]['iname']
        if self.semester < 'S19B':
            if val <= self.transparency_from_ph1:
                progFile.logger.info('Line %d, column %s of sheet %s: %s value %s is less than or equal to %s and is ok' % (row_num, col_name, self.name, iname, val, self.transparency_from_ph1))
            else:
                msg = "Error while checking line %d, column %s of sheet %s: %s value %s must be less than or equal to %s (Transparency from Phase 1)" % (row_num, iname, self.name, iname, val, self.transparency_from_ph1)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([row_num, [iname], msg])
                progFile.error_count += 1
        else:
            if val in self.transparency_choices and val <= self.transparency_from_ph1:
                progFile.logger.info('Line %d, column %s of sheet %s: %s value %s is in %s and is less than or equal to %s and is ok' % (row_num, col_name, self.name, iname, val, self.transparency_choices, self.transparency_from_ph1))
            elif val not in self.transparency_choices and val <= self.transparency_from_ph1:
                msg = "Warning while checking line %d, column %s of sheet %s: %s value %s should be one of %s. %s value %s is less than or equal to %s and is ok" % (row_num, iname, self.name, iname, val, self.transparency_choices, iname, val, self.transparency_from_ph1)
                progFile.logger.warning(msg)
                progFile.warnings[self.name].append([row_num, [iname], msg])
                progFile.warn_count += 1

            elif val in self.transparency_choices and val > self.transparency_from_ph1:
                msg = "Error while checking line %d, column %s of sheet %s: %s value %s is in %s. However, %s value %s must be less than or equal to %s (Transparency from Phase 1)" % (row_num, iname, self.name, iname, val, self.transparency_choices, iname, val, self.transparency_from_ph1)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([row_num, [iname], msg])
                progFile.error_count += 1

            elif val not in self.transparency_choices and val > self.transparency_from_ph1:
                msg = "Error while checking line %d, column %s of sheet %s: %s value %s should be one of %s. Also, %s value %s must be less than or equal to %s (Transparency from Phase 1)" % (row_num, iname, self.name, iname, val, self.transparency_choices, iname, val, self.transparency_from_ph1)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([row_num, [iname], msg])
                progFile.error_count += 1

    def moon_check(self, val, rec, row_num, col_name, progFile):
        ph1MoonConstraint = progFile.cfg['proposal'].proposal_info['ph1_moon']
        iname = self.columnInfo[col_name]['iname']

        allowed_moon_states = moon_states[ph1MoonConstraint.lower()]
        if val.lower() in allowed_moon_states:
            progFile.logger.debug('Line %d, column %s of sheet %s: %s %s found in %s' % (row_num, col_name, self.name, col_name, val, allowed_moon_states))
        else:
            msg = 'Error while checking line %d, column %s of sheet %s: %s value %s is not one of the allowed moon states for Phase 1 Moon constraint %s; allowed values are: %s' % (row_num, iname, self.name, iname, val, ph1MoonConstraint, allowed_moon_states)
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [iname], msg])
            progFile.error_count += 1
            return

    def moon_sep_check(self, val, rec, row_num, col_name, progFile):
        iname = self.columnInfo[col_name]['iname']
        # Produce a warning if the requested moon separation distance
        # is less than the warning level.
        if val >= moon_sep_dist_warn:
            progFile.logger.debug('Line %d, column %s of sheet %s: %s %s is ok' % (row_num, col_name, self.name, col_name, val))
        else:
            msg = 'Warning while checking line %d, column %s of sheet %s: %s value %s deg is less than minimum moon separation distance %s deg' % (row_num, iname, self.name, iname, val, moon_sep_dist_warn)
            progFile.logger.warning(msg)
            progFile.warnings[self.name].append([row_num, [iname], msg])
            progFile.warn_count += 1

class TgtCfgFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        self.name = 'targets'
        self.tgt_cfgs = {}
        self.column_map = {
            'code': 'code',
            'target_name': 'name',
            'ra': 'ra',
            'dec': 'dec',
            'equinox': 'eq',
            'sdss_ra': 'sdss_ra',
            'sdss_dec': 'sdss_dec',
            'comment': 'comment',
            }
        self.columnInfo = {
            'code':         {'iname': 'Code',        'type': str, 'constraint': "len(value) > 0",              'prefilled': False, 'required': True},
            'target_name':  {'iname': 'Target Name', 'type': str, 'constraint': "len(value) > 0",              'prefilled': False, 'required': True},
            'ra':           {'iname': 'RA',          'type': str, 'constraint': self.parseRA_Dec,              'prefilled': False, 'required': True},
            'dec':          {'iname': 'DEC',         'type': str, 'constraint': self.parseRA_Dec,              'prefilled': False, 'required': True},
            'equinox':      {'iname': 'Equinox',     'type': str, 'constraint': "value in ('J2000', 'B1950')", 'prefilled': False, 'required': True},
            'sdss_ra':      {'iname': 'SDSS RA',     'type': str, 'constraint': self.parseRA_Dec,              'prefilled': False, 'required': False},
            'sdss_dec':     {'iname': 'SDSS DEC',    'type': str, 'constraint': self.parseRA_Dec,              'prefilled': False, 'required': False},
            }
        super(TgtCfgFile, self).__init__(input_dir, 'targets', logger, file_ext)

    def parseRA_Dec(self, val, rec, row_num, col_name, progFile):
        iname = self.columnInfo[col_name]['iname']
        valid = False
        if len(val) > 0:
            if 'ra' in col_name:
                valid = self.parseRA(val)
            elif 'dec' in col_name:
                valid = self.parseDec(val)
            if valid:
                progFile.logger.debug('Line %d, column %s of sheet %s: %s %s is ok' % (row_num, iname, self.name, iname, val))
        else:
            # Columns sdss_ra and sdss_dec are allowed to be blank,
            # but report a warning message if they are blank.
            if col_name in ('sdss_ra', 'sdss_dec'):
                msg = 'Warning while checking line %d, column %s of sheet %s: %s is blank' % (row_num, iname, self.name, iname)
                progFile.logger.warning(msg)
                progFile.warnings[self.name].append([row_num, [iname], msg])
                progFile.warn_count += 1
                valid = True
        if not valid:
            msg = "Error while checking line %d, column %s of sheet %s: %s '%s' is not valid" % (row_num, iname, self.name, iname, val)
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [iname], msg])
            progFile.error_count += 1
        return valid

    def parseRA(self, ra):
        try:
            datetime.datetime.strptime(ra, '%H:%M:%S')
        except ValueError:
            try:
                datetime.datetime.strptime(ra, '%H:%M:%S.%f')
            except ValueError:
                return False
        return True

    def parseDec(self, dec):
        dms = dec.split(':')
        d = dms.pop(0)
        try:
            d = float(d)
        except ValueError:
            return False
        try:
            assert d >= -90.0 and d <= 90.0
        except AssertionError:
            return False
        ms = ':'.join(dms)
        try:
            datetime.datetime.strptime(ms, '%M:%S')
        except ValueError:
            try:
                datetime.datetime.strptime(ms, '%M:%S.%f')
            except ValueError:
                return False
        return True

    def parse_input(self):
        """
        Read all target configurations from a CSV file.
        """
        self.queue_file.seek(0)
        old_cfgs = self.tgt_cfgs
        self.tgt_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments and 'default' line
                if row[0].lower() in ('comment', 'default'):
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                #target = entity.StaticTarget()
                target = entity.HSCTarget()
                code = target.import_record(rec)

                # update existing old record if it exists
                # since OBs may be pointing to it
                if code in old_cfgs:
                    new_cfg = target
                    target = old_cfgs[code]
                    target.__dict__.update(new_cfg.__dict__)

                self.tgt_cfgs[code] = target

            except Exception as e:
                raise ValueError("Error reading line %d of target configuration from file %s: %s" % (
                    lineNum, self.filepath, str(e)))


class InsCfgFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        self.name = 'inscfg'
        self.ins_cfgs = {}


        # All instrument configs should have at least these
        self.column_map = { 'code': 'code',
                            'instrument': 'insname',
                            'mode': 'mode',
                            };
        self.configs = {
            'HSC': (entity.HSCConfiguration,
                      { 'code': 'code',
                        'instrument': 'insname',
                        'mode': 'mode',
                        'filter': 'filter',
                        'exp_time': 'exp_time',
                        'num_exp': 'num_exp',
                        'dither': 'dither',
                        'guiding': 'guiding',
                        'pa': 'pa',
                        'offset_ra': 'offset_ra',
                        'offset_dec': 'offset_dec',
                        'dith1': 'dith1',
                        'dith2': 'dith2',
                        'skip': 'skip',
                        'stop': 'stop',
                        'on_src_time': 'on_src_time',
                        'total_time': 'total_time',
                        'comment': 'comment',
                        }),
            }

        self.HSC_modes = "('imaging', 'dark')".upper()

        self.readoutOverheadAllInst = {'HSC': 40}

        self.dither_constr = "value in ('1', '5', 'N')"
        self.guiding_constr = "value in ('Y','N')"
        self.columnInfoAllInst = {
            'HSC': {
            'code':         {'iname': 'Code',       'type': str,   'constraint': "len(value) > 0",                 'prefilled': False, 'required': True},
            'instrument':   {'iname': 'Instrument', 'type': str,   'constraint': "value == 'HSC'",                 'prefilled': False, 'required': True},
            'mode':         {'iname': 'Mode',       'type': str,   'constraint': "value in %s" % self.HSC_modes,   'prefilled': False, 'required': True},
            'filter':       {'iname': 'Filter',     'type': str,   'constraint': self.filterCheck,                 'prefilled': False, 'required': True},
            'exp_time':     {'iname': 'Exp Time',   'type': float, 'constraint': "value > 0.0",                    'prefilled': False, 'required': True},
            'num_exp':      {'iname': 'Num Exp',    'type': int,   'constraint': "value > 0",                      'prefilled': False, 'required': True},
            'dither':       {'iname': 'Dither',     'type': str,   'constraint': self.dither_constr,               'prefilled': False, 'required': True},
            'guiding':      {'iname': 'Guiding',    'type': str,   'constraint': self.guiding_constr,              'prefilled': False, 'required': True},
            'pa':           {'iname': 'PA',         'type': float, 'constraint': None,                             'prefilled': False, 'required': True},
            'offset_ra':    {'iname': 'Offset RA',  'type': float, 'constraint': None,                             'prefilled': False, 'required': True},
            'offset_dec':   {'iname': 'Offset DEC', 'type': float, 'constraint': None,                             'prefilled': False, 'required': True},
            'dith1':        {'iname': 'Dith1',      'type': float, 'constraint': None,                             'prefilled': False, 'required': True},
            'dith2':        {'iname': 'Dith2',      'type': float, 'constraint': None,                             'prefilled': False, 'required': True},
            'skip':         {'iname': 'Skip',       'type': int,   'constraint': None,                             'prefilled': False, 'required': True},
            'stop':         {'iname': 'Stop',       'type': int,   'constraint': self.stopCheck,                   'prefilled': True,  'required': True},
            'on_src_time':  {'iname': 'On-src Time','type': float, 'constraint': self.onSrcTimeCalcCheck,          'prefilled': True,  'required': True},
            'total_time':   {'iname': 'Total Time', 'type': float, 'constraint': self.totalTimeCalcCheck,          'prefilled': True,  'required': True},
            },
            }
        # If "proposal" sheet supplies a "Maximum OB Length" value,
        # max_onsource_time_mins will get overwritten by that value in
        # the update_constraints method
        self.max_onsource_time_mins = 100.0 # minutes
        super(InsCfgFile, self).__init__(input_dir, 'inscfg', logger, file_ext)
        self.excel_converters = {
            'Num Exp':    lambda x: x if pd.isnull(x) or isinstance(x, str) else int(x),
            'Dither':     lambda x: '' if pd.isnull(x) else str(x),
            'Skip':       lambda x: x if pd.isnull(x) or isinstance(x, str) else int(x),
            'Stop':       lambda x: x if pd.isnull(x) or isinstance(x, str) else int(x)}

        self.semester = None

    def parse_input(self):
        """
        Read all instrument configurations from a CSV file.
        """
        self.queue_file.seek(0)
        old_cfgs = self.ins_cfgs
        self.ins_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments and 'default' line
                if row[0].lower() in ('comment', 'default'):
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                insname = rec.insname.upper()
                klass, col_map = self.configs[insname]
                # reparse row now that we know what kind of items to expect
                rec = self.parse_row(row, self.columnNames,
                                     col_map)
                # Special case For Y2016: some observers might have
                # specified earlier versions of i or r filters. Silently
                # upgrade these to ver 2
                if self.semester[:3] in ('S16', 'S17'):
                    rec.filter = 'i2' if rec.filter == 'i' else rec.filter
                    rec.filter = 'r2' if rec.filter == 'r' else rec.filter

                inscfg = klass()
                code = inscfg.import_record(rec)

                # update existing old record if it exists
                # since OBs may be pointing to it
                if code in old_cfgs:
                    new_cfg = inscfg
                    inscfg = old_cfgs[code]
                    inscfg.__dict__.update(new_cfg.__dict__)

                self.ins_cfgs[code] = inscfg

            except Exception as e:
                raise ValueError("Error reading line %d of instrument configuration from file %s: %s" % (
                    lineNum, self.filepath, str(e)))

    def update_constraints(self, proposal_info):
        try:
            self.max_onsource_time_mins =  float(proposal_info['maximum_ob_length']) / 60.0
        except KeyError:
            # If "proposal" sheet did not have "Maximum OB Length"
            # column, ignore the error and leave
            # max_onsource_time_mins as the default value.
            pass
        self.logger.debug('max_onsource_time_mins is %s' % self.max_onsource_time_mins)

    def get_insname(self):
        # Access the inscfg information to determine the instrument
        # name. Hopefully, the first row has the column names and the
        # second row is parseable so that we can get the instrument
        # name.
        self.stringio[self.name].seek(0)
        reader = csv.reader(self.stringio[self.name], **self.fmtparams)
        column_names = next(reader)
        insname = ''
        count = 0
        search_limit = 20
        # Search the first 20 lines to identify the instrument name
        while len(insname.strip()) < 1 and count < search_limit:
            row = next(reader)
            count += 1
            rec = self.parse_row(row, column_names, self.column_map)
            insname = rec.insname
        return insname

    def validate_column_names(self, progFile):
        insname = self.get_insname()
        self.columnInfo = self.columnInfoAllInst[insname]
        return super(InsCfgFile, self).validate_column_names(progFile)

    def checkCodesUnique(self, progFile):
        insname = self.get_insname()
        self.columnInfo = self.columnInfoAllInst[insname]
        return super(InsCfgFile, self).checkCodesUnique(progFile)

    def validate_datatypes(self, progFile):
        insname = self.get_insname()
        self.column_map = self.configs[insname][1]
        self.columnInfo = self.columnInfoAllInst[insname]
        self.readoutOverhead = self.readoutOverheadAllInst[insname]
        return super(InsCfgFile, self).validate_datatypes(progFile)

    def validate_data(self, progFile, propname):
        prop_split = propname.split('-')
        self.semester = prop_split[0]
        self.insname = self.get_insname()
        self.column_map = self.configs[self.insname][1]
        self.columnInfo = self.columnInfoAllInst[self.insname]
        return super(InsCfgFile, self).validate_data(progFile)

    def stopCheck(self, val, rec, row_num, col_name, progFile):
        num_exp = int(rec.num_exp)
        skip = int(rec.skip)
        stop = int(rec[col_name])
        iname = self.columnInfo[col_name]['iname']
        if stop > skip:
            progFile.logger.debug('Line %d, column %s of sheet %s: %s value %d is greater than Skip value of %d and is ok' % (row_num, iname, self.name, iname, stop, skip))
        else:
            msg = 'Error while checking line %d, column %s of sheet %s: %s value %d is less than or equal to Skip value of %d' % (row_num, iname, self.name, iname, stop, skip)
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [iname], msg])
            progFile.error_count += 1

        if stop >= num_exp:
            progFile.logger.debug('Line %d, column %s of sheet %s: %s value %d is greater than or equal to Num Exp value of %d and is ok' % (row_num, iname, self.name, iname, stop, num_exp))
        else:
            msg = 'Warning while checking line %d, column %s of sheet %s: %s value %d is less than Num Exp value of %d' % (row_num, iname, self.name, iname, stop, num_exp)
            progFile.logger.warning(msg)
            progFile.warnings[self.name].append([row_num, [iname], msg])
            progFile.warn_count += 1

    def onSrcTimeCalcCheck(self, val, rec, row_num, col_name, progFile):
        num_exp = int(rec.num_exp)
        exp_time = float(rec.exp_time)
        skip = int(rec.skip)
        stop = int(rec.stop)
        calc_time = (num_exp - (num_exp - stop) - skip) * exp_time
        iname = self.columnInfo[col_name]['iname']
        if calc_time == float(rec[col_name]):
            progFile.logger.debug('Line %d, column %s of sheet %s: Computed on-source time %s seconds equals the %s value of %s seconds and is ok' % (row_num, iname, self.name, calc_time, iname, rec.on_src_time))
        else:
            msg = 'Error while checking line %d, column %s of sheet %s: Total on-source time %s seconds is different from the %s value of %s seconds' % (row_num, iname, self.name, calc_time, iname, rec[col_name])
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [self.columnInfo['exp_time']['iname'], self.columnInfo['num_exp']['iname'], self.columnInfo['stop']['iname'], self.columnInfo['skip']['iname'], iname], msg])
            progFile.error_count += 1

        onsource_time_mins = float(calc_time) / 60.0
        if onsource_time_mins <= self.max_onsource_time_mins:
            progFile.logger.info('Line %d, column %s of sheet %s: onsource time of %.1f minutes is less than maximum allowed duration of %.1f minutes and is ok' % (row_num, iname, self.name, onsource_time_mins, self.max_onsource_time_mins))
        else:
            msg = 'Error while checking line %d, column %s of sheet %s: onsource time of %.1f minutes exceeds maximum allowed duration of %.1f minutes' % (row_num, iname, self.name, onsource_time_mins, self.max_onsource_time_mins)
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [self.columnInfo['exp_time']['iname'], self.columnInfo['num_exp']['iname'], self.columnInfo['stop']['iname'], self.columnInfo['skip']['iname']], msg])
            progFile.error_count += 1

    def totalTimeCalcCheck(self, val, rec, row_num, col_name, progFile):
        num_exp = int(rec.num_exp)
        exp_time = float(rec.exp_time)
        skip = int(rec.skip)
        stop = int(rec.stop)
        calc_time = (num_exp - (num_exp - stop) - skip) * (exp_time + self.readoutOverhead)
        iname = self.columnInfo[col_name]['iname']
        if calc_time == float(rec[col_name]):
            progFile.logger.debug('line %d, column %s of sheet %s: Computed total time %s seconds equals the %s value of %s seconds and is ok' % (row_num, iname, self.name, calc_time, iname, rec.on_src_time))
        else:
            msg = 'Error while checking line %d, column %s of sheet %s: Total total time %s seconds is different from the %s value of %s seconds' % (row_num, iname, self.name, calc_time, iname, rec[col_name])
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [self.columnInfo['exp_time']['iname'], self.columnInfo['num_exp']['iname'], self.columnInfo['stop']['iname'], self.columnInfo['skip']['iname'], iname], msg])
            progFile.error_count += 1

    def filterCheck(self, val, rec, row_num, col_name, progFile):
        iname = self.columnInfo[col_name]['iname']
        if self.insname == 'HSC':
            if have_HSC_cfg:
                if val in HSC_cfg.all_filters:
                    progFile.logger.debug('line %d, column %s of sheet %s: filter %s is ok' % (row_num, iname, self.name, rec.filter))
                else:
                    msg = 'Error while checking line %d, column %s of sheet %s: filter %s not in list %s' % (row_num, iname, self.name, val, HSC_cfg.all_filters)
                    progFile.logger.error(msg)
                    progFile.errors[self.name].append([row_num, [self.columnInfo['filter']['iname']], msg])
                    progFile.error_count += 1
                if val in HSC_cfg.semester_filters[self.semester]:
                    progFile.logger.debug('line %d, column %s of sheet %s: filter %s is in semester %s list and is ok' % (row_num, iname, self.name, rec.filter, self.semester))
                else:
                    msg = 'Warning while checking line %d, column %s of sheet %s: filter %s not in semester %s list %s' % (row_num, iname, self.name, val, self.semester, HSC_cfg.semester_filters[self.semester])
                    progFile.logger.warning(msg)
                    progFile.warnings[self.name].append([row_num, [self.columnInfo['filter']['iname']], msg])
                    progFile.warn_count += 1
            else:
                msg = 'Error while checking line %d, column %s of sheet %s: filter configuration file not available' % (row_num, iname, self.name)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([row_num, [self.columnInfo['filter']['iname']], msg])
                progFile.error_count += 1

class OBListFile(QueueFile):
    def __init__(self, input_dir, logger, propname, propdict,
                 telcfgs, tgtcfgs, inscfgs, envcfgs, file_ext=None):
        self.name = 'ob'
        # obs_info is the list of OB objects that will be used by the
        # observing block scheduling functions.
        self.obs_info = []
        self.proposal = propname.upper()
        # lookup tables
        self.propdict = propdict
        self.telcfgs = telcfgs
        self.tgtcfgs = tgtcfgs
        self.inscfgs = inscfgs
        self.envcfgs = envcfgs

        self.column_map = {
            'code': 'code',
            'tgtcfg': 'tgt_code',
            'inscfg': 'ins_code',
            'calib_tgtcfg': 'calib_tgt_code',
            'calib_inscfg': 'calib_ins_code',
            'telcfg': 'tel_code',
            'envcfg': 'env_code',
            'priority': 'priority',
            'on_src_time': 'on_src_time',
            'total_time': 'total_time',
            'acct_time': 'acct_time',
            'extra_params': 'extra_params',
            'comment': 'comment',
            }
        self.columnInfo = {
            'code':       {'iname': 'Code',       'type': str,   'constraint': "len(value) > 0",    'prefilled': False, 'required': True},
            'tgtcfg':     {'iname': 'tgtcfg',     'type': str,   'constraint': self.tgtcfgCheck,    'prefilled': False, 'required': True},
            'inscfg':     {'iname': 'inscfg',     'type': str,   'constraint': self.inscfgCheck,    'prefilled': False, 'required': True},
            'calib_tgtcfg': {'iname': 'calib_tgtcfg', 'type': str, 'constraint': self.calibTgtcfgCheck, 'prefilled': False, 'required': False},
            'calib_inscfg': {'iname': 'calib_inscfg', 'type': str, 'constraint': self.calibInscfgCheck, 'prefilled': False, 'required': False},
            'telcfg':     {'iname': 'telcfg',     'type': str,   'constraint': self.telcfgCheck,    'prefilled': False, 'required': True},
            'envcfg':     {'iname': 'envcfg',     'type': str,   'constraint': self.envcfgCheck,    'prefilled': False, 'required': True},
            'priority':   {'iname': 'Priority',   'type': float, 'constraint': None,                'prefilled': False, 'required': True},
            'on_src_time':{'iname': 'On-src Time','type': float, 'constraint': self.checkOnSrcTime, 'prefilled': True,  'required': True},
            'total_time': {'iname': 'Total Time', 'type': float, 'constraint': self.checkTotalTime, 'prefilled': True,  'required': True},
            'acct_time':  {'iname': 'Acct Time',  'type': float, 'constraint': None,                 'prefilled': True,  'required': False},
            }
        super(OBListFile, self).__init__(input_dir, 'ob', logger, file_ext=file_ext)

    def cfgCheck(self, val, rec, row_num, col_name, progFile, cfg_name, cfg):
        iname = self.columnInfo[col_name]['iname']
        if val in cfg:
            progFile.logger.debug('Line %d, column %s of sheet %s: found %s %s in %s sheet' % (row_num, iname, self.name, col_name, val, cfg_name))
        else:
            msg = "Error while checking line %d, column %s of sheet %s: %s '%s' does not appear in %s sheet" % (row_num, iname, self.name, col_name, val, cfg_name)
            progFile.logger.error(msg)
            progFile.errors[self.name].append([row_num, [iname], msg])
            progFile.error_count += 1

    def tgtcfgCheck(self, val, rec, row_num, col_name, progFile):
        cfg_name = 'targets'
        self.cfgCheck(val, rec, row_num, col_name, progFile, cfg_name, progFile.cfg[cfg_name].tgt_cfgs)

    def calibTgtcfgCheck(self, val, rec, row_num, col_name, progFile):
        cfg_name = 'targets'
        iname = self.columnInfo[col_name]['iname']
        if val == 'DEFAULT':
            progFile.logger.debug('Line %d, column %s of sheet %s: value %s is OK' % (row_num, iname, self.name, val))
        elif len(val) == 0:
            progFile.logger.debug('Line %d, column %s of sheet %s: blank value is OK' % (row_num, iname, self.name))
        else:
            self.cfgCheck(val, rec, row_num, col_name, progFile, cfg_name, progFile.cfg[cfg_name].tgt_cfgs)

    def inscfgCheck(self, val, rec, row_num, col_name, progFile):
        cfg_name = 'inscfg'
        self.cfgCheck(val, rec, row_num, col_name, progFile, cfg_name, progFile.cfg[cfg_name].ins_cfgs)

    def calibInscfgCheck(self, val, rec, row_num, col_name, progFile):
        cfg_name = 'inscfg'
        iname = self.columnInfo[col_name]['iname']
        if val == 'DEFAULT':
            progFile.logger.debug('Line %d, column %s of sheet %s: value %s is OK' % (row_num, iname, self.name, val))
        elif len(val) == 0:
            progFile.logger.debug('Line %d, column %s of sheet %s: blank value is OK' % (row_num, iname, self.name))
        else:
            self.cfgCheck(val, rec, row_num, col_name, progFile, cfg_name, progFile.cfg[cfg_name].ins_cfgs)

    def telcfgCheck(self, val, rec, row_num, col_name, progFile):
        cfg_name = 'telcfg'
        self.cfgCheck(val, rec, row_num, col_name, progFile, cfg_name, progFile.cfg[cfg_name].tel_cfgs)

    def envcfgCheck(self, val, rec, row_num, col_name, progFile):
        cfg_name = 'envcfg'
        self.cfgCheck(val, rec, row_num, col_name, progFile, cfg_name, progFile.cfg[cfg_name].env_cfgs)

    def checkTime(self, val, rec, row_num, col_name, progFile, inscfg_col_name):
        iname = self.columnInfo[col_name]['iname']
        inscfg_name = 'inscfg'
        iname_inscfg = progFile.cfg[inscfg_name].columnInfo[inscfg_col_name]['iname']
        for row in progFile.cfg[inscfg_name].rows:
            if rec.ins_code == row['Code']:
                if val == float(row[iname_inscfg]):
                    progFile.logger.debug('Line %d, column %s of sheet %s: %s %s seconds on ob sheet equals the %s value of %s seconds for Code %s and is ok' % (row_num, iname, self.name, iname, val, iname_inscfg, row[iname_inscfg], rec.ins_code))
                else:
                    msg = 'Error while checking line %d, column %s of sheet %s: %s %s seconds on ob sheet is different from the %s value of %s seconds for Code %s' % (row_num, iname, self.name, iname, val, iname_inscfg, row[iname_inscfg], rec.ins_code)
                    progFile.logger.error(msg)
                    progFile.errors[self.name].append([row_num, [iname], msg])
                    progFile.error_count += 1

    def checkOnSrcTime(self, val, rec, row_num, col_name, progFile):
        inscfg_col_name = 'on_src_time'
        self.checkTime(val, rec, row_num, col_name, progFile, inscfg_col_name)

    def checkTotalTime(self, val, rec, row_num, col_name, progFile):
        inscfg_col_name = 'total_time'
        self.checkTime(val, rec, row_num, col_name, progFile, inscfg_col_name)

    def calibCheck(self, progFile):
        # Check calib_tgt_code and calib_ins_code to make sure they
        # are either both specified or both empty. Otherwise, report
        # an error.
        begin_error_count = progFile.error_count

        # First, get the column names from the first row.
        self.stringio[self.name].seek(0)
        reader = csv.reader(self.stringio[self.name], **self.fmtparams)
        column_names = next(reader)
        for i, row in enumerate(reader):
            row_num = i + 1
            rec = self.parse_row(row, column_names, self.column_map)

            # Ignore comment rows
            if self.ignoreRow(row, rec):
                progFile.logger.debug('On Sheet %s, ignore Line %d with contents %s' % (self.name, row_num, row))

            else:
                # Check calib_tgt_code and calib_ins_code only if both
                # items are in rec.
                if rec.has_key('calib_tgt_code') and rec.has_key('calib_ins_code'):
                    calib_tgt_code_len = len(rec.calib_tgt_code)
                    calib_ins_code_len = len(rec.calib_ins_code)
                    if calib_tgt_code_len == 0 and calib_ins_code_len == 0:
                        progFile.logger.debug('Line %d, columns calib_tgtcfg and calib_inscfg of sheet %s: are both empty and are ok' % (row_num, self.name))
                    elif calib_tgt_code_len > 0 and calib_ins_code_len > 0:
                        progFile.logger.debug('Line %d, columns calib_tgtcfg and calib_inscfg of sheet %s: are both non-empty and are ok' % (row_num, self.name))
                    elif calib_tgt_code_len > 0 and calib_ins_code_len == 0:
                        val = rec.calib_tgt_code
                        iname = self.columnInfo['calib_inscfg']['iname']
                        msg = 'Error while checking line %d, columns calib_tgtcfg and calib_inscfg of sheet %s: calib_tgtcfg is %s but calib_inscfg is empty' % (row_num, self.name, val)
                        progFile.logger.error(msg)
                        progFile.errors[self.name].append([row_num, [iname], msg])
                        progFile.error_count += 1
                    elif  calib_tgt_code_len == 0 and calib_ins_code_len > 0:
                        val = rec.calib_ins_code
                        iname = self.columnInfo['calib_tgtcfg']['iname']
                        msg = 'Error while checking line %d, columns calib_tgtcfg and calib_inscfg of sheet %s: calib_tgtcfg is empty but calib_inscfg is %s' % (row_num, self.name, val)
                        progFile.logger.error(msg)
                        progFile.errors[self.name].append([row_num, [iname], msg])
                        progFile.error_count += 1

    # TODO: I think totalOnSrcTimeCheck is obsolete
    def totalOnSrcTimeCheck(self, progFile):
        # Add up the on-source time for all the observing blocks in
        # the file and check to see if the total is less than or equal
        # to the allocated on-source time specified on the "proposal"
        # sheet.

        begin_error_count = progFile.error_count

        # First, get the column names from the first row.
        self.stringio[self.name].seek(0)
        reader = csv.reader(self.stringio[self.name], **self.fmtparams)
        column_names = next(reader)

        onSrcTimeSum = 0.0
        for i, row in enumerate(reader):
            progFile.logger.debug('Sheet %s Line %d Row is %s' % (self.name, i+1, row))
            row_num = i + 1
            rec = self.parse_row(row, column_names, self.column_map)

            # Ignore comment rows
            if self.ignoreRow(row, rec):
                progFile.logger.debug('On Sheet %s, ignore Line %d with contents %s' % (self.name, row_num, row))

            else:
                onSrcTimeSum += float(rec.on_src_time)

        iname = self.columnInfo['on_src_time']['iname']
        ph1_allocated_time = float(progFile.cfg['proposal'].proposal_info['allocated_time'])
        # Round onSrcTimeSum and ph1_allocated_time to nearest 0.1
        # second to avoid roundoff errors when comparing the two
        # values.
        onSrcTimeSum = round(onSrcTimeSum,1)
        ph1_allocated_time = round(ph1_allocated_time,1)
        # Compare onSrcTimeSum to ph1_allocated_time and report error
        # if onSrcTimeSum is greater than ph1_allocated_time
        if onSrcTimeSum < ph1_allocated_time:
            msg = 'Warning while checking column %s of sheet %s: On-source time sum of %s seconds is less than the Phase 1 allocated value of %s seconds' % (iname, self.name, onSrcTimeSum, ph1_allocated_time )
            progFile.logger.warning(msg)
            progFile.warnings[self.name].append([None, [iname], msg])
            progFile.warn_count += 1
        elif onSrcTimeSum == ph1_allocated_time:
            progFile.logger.debug('Column %s of sheet %s: On-source time sum of %s seconds is equal to the Phase 1 allocated value of %s seconds and is ok' % (iname, self.name, onSrcTimeSum, ph1_allocated_time))
        else:
            msg = 'Warning while checking column %s of sheet %s: On-source time sum of %s seconds is greater than the Phase 1 allocated value of %s seconds' % (iname, self.name, onSrcTimeSum, ph1_allocated_time )
            progFile.logger.warning(msg)
            progFile.warnings[self.name].append([None, [iname], msg])
            progFile.warn_count += 1

    def getTotalTime(self, progfile, iname):

        totalTime = None

        # We don't need to look through the entire set of rows. We
        # should be able to locate the string withing the first
        # "max_search_rows".
        max_search_rows = 50

        self.stringio[self.name].seek(0)
        queue_file = self.stringio[self.name]
        reader = csv.reader(queue_file, **self.fmtparams)

        # skip header
        next(reader)

        # Iterate through rows and look for the row that has a string
        # that matches the iname value.
        tt_row = None
        tt_col = None
        for i, row in enumerate(reader):
            for j, item in enumerate(row):
                if item == iname:
                    tt_row = i
                    tt_col = j
                    break
            if tt_row or i > max_search_rows:
                break

        if tt_row and tt_col:
            row = next(reader)
            totalTime_str = row[tt_col]
            try:
                totalTime = float(totalTime_str)
            except ValueError as e:
                msg = 'Error while checking sheet %s: Could not convert {} {} to a numerical value'.format(self.name, iname, totalTime_str)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([None, [iname], msg])
                progFile.error_count += 1

        return totalTime

    # TODO: I think totalTimeCheck is obsolete
    def totalTimeCheck(self, progFile, iname):

        # We don't need to look through the entire set of rows. We
        # should be able to locate the string withing the first
        # "max_search_rows".
        max_search_rows = 50

        self.stringio[self.name].seek(0)
        queue_file = self.stringio[self.name]
        reader = csv.reader(queue_file, **self.fmtparams)

        # skip header
        next(reader)

        # Iterate through rows and look for the row that has a string
        # that matches the iname value.
        tt_row = None
        tt_col = None
        for i, row in enumerate(reader):
            for j, item in enumerate(row):
                if item == iname:
                    tt_row = i
                    tt_col = j
                    break
            if tt_row or i > max_search_rows:
                break

        if tt_row and tt_col:

            row = next(reader)
            totalTime_str = row[tt_col]

            try:
                totalTime = float(totalTime_str)
            except ValueError as e:
                msg = 'Error while checking sheet %s: Could not convert {} {} to a numerical value'.format(self.name, iname, totalTime_str)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([None, [iname], msg])
                progFile.error_count += 1

            ph1_allocated_time_str = progFile.cfg['proposal'].proposal_info['allocated_time']
            try:
                ph1_allocated_time = float(progFile.cfg['proposal'].proposal_info['allocated_time'])
            except ValueError as e:
                msg = 'Error while checking sheet %s: Could not convert Phase 1 Allocated Time {} to a numerical value'.format(self.name, ph1_allocated_time_str)
                progFile.logger.error(msg)
                progFile.errors[self.name].append([None, [iname], msg])
                progFile.error_count += 1

            ph1_allocated_time = round(ph1_allocated_time,1)
            # Compare totalTime to ph1_allocated_time and report
            # warning if totalTime is greater than ph1_allocated_time
            if totalTime < ph1_allocated_time:
                msg = 'Warning while checking sheet {}: {} of {} seconds is less than the Phase 1 allocated value of {} seconds'.format(self.name, iname, totalTime, ph1_allocated_time)
                progFile.logger.warning(msg)
                progFile.warnings[self.name].append([None, [iname], msg])
                progFile.warn_count += 1
            elif totalTime == ph1_allocated_time:
                progFile.logger.debug('Sheet {}: {} of {} seconds is equal to the Phase 1 allocated value of {} seconds and is ok'.format(self.name, iname, totalTime, ph1_allocated_time))
            else:
                msg = 'Warning while checking sheet {}: {} of {} seconds is greater than the Phase 1 allocated value of {} seconds'.format(self.name, iname, totalTime, ph1_allocated_time)
                progFile.logger.warning(msg)
                progFile.warnings[self.name].append([None, [iname], msg])
                progFile.warn_count += 1
            return True
        else:
            self.logger.info('String {} not found in ob sheet'.format(iname))
            return False

    def parse_input(self):
        """
        Read all observing blocks from a CSV file.
        """
        self.queue_file.seek(0)
        self.obs_info = []
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                first_col_content = row[0].strip()
                if first_col_content.lower() == 'comment' or \
                   (len(first_col_content) > 0 and first_col_content[0] == '#'):
                    continue
                # skip blank lines
                if len(first_col_content) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                code = rec.code.strip()

                program = self.propdict[self.proposal]
                envcfg = self.envcfgs[rec.env_code.strip()]
                telcfg = self.telcfgs[rec.tel_code.strip()]
                tgtcfg = self.tgtcfgs[rec.tgt_code.strip()]
                inscfg = self.inscfgs[rec.ins_code.strip()]

                if rec.has_key('calib_tgt_code'):
                    calib_tgt_code =  rec.calib_tgt_code.strip()
                    if calib_tgt_code == 'default':
                        calib_tgtcfg = calib_tgt_code
                    elif len(calib_tgt_code) == 0:
                        calib_tgtcfg = None
                    else:
                        calib_tgtcfg = self.tgtcfgs[calib_tgt_code]
                else:
                    calib_tgtcfg = None

                if rec.has_key('calib_ins_code'):
                    calib_ins_code =  rec.calib_ins_code.strip()
                    if calib_ins_code == 'default':
                        calib_inscfg = calib_ins_code
                    elif len(calib_ins_code) == 0:
                        calib_inscfg = None
                    else:
                        calib_inscfg = self.inscfgs[calib_ins_code]
                else:
                    calib_inscfg = None

                priority = 1.0
                if rec.priority != None:
                    priority = float(rec.priority)

                # for HSC SSP--special extra params to be passed to OPE
                # file generation
                extra_params = ''
                if rec.has_key('extra_params'):
                    extra_params = rec.extra_params.strip()

                comment = ''
                if rec.has_key('comment'):
                    comment = rec.comment.strip()

                if rec.has_key('acct_time'):
                    acct_time = float(rec.acct_time)
                else:
                    # NOTE: As of S21B we are now charging the
                    # user for instrument overheads (used to be):
                    # acct_time=float(rec.on_src_time),
                    # NOTE: 2021-01-11 EJ  As of S22A,
                    # added extra overhead charge
                   acct_time = (float(rec.total_time) * hsc_extra_overhead_factor)

                ob = entity.HSC_OB(id=code,
                                   program=program,
                                   target=tgtcfg,
                                   inscfg=inscfg,
                                   envcfg=envcfg,
                                   telcfg=telcfg,
                                   calib_tgtcfg=calib_tgtcfg,
                                   calib_inscfg=calib_inscfg,
                                   priority=priority,
                                   name=code,
                                   total_time=float(rec.total_time),
                                   acct_time=acct_time,
                                   comment=comment,
                                   extra_params=extra_params)
                self.obs_info.append(ob)

            except Exception as e:
                raise ValueError("Error reading line %d of oblist from file %s: %s" % (
                    lineNum, self.filepath, str(e)))

class ProgramFile(QueueFile):
    def __init__(self, input_dir, logger, propname, propdict, file_ext=None, file_obj=None):
        super(ProgramFile, self).__init__(input_dir, propname, logger, file_ext)
        self.requiredSheets = ('telcfg', 'inscfg', 'envcfg', 'targets', 'ob', 'proposal')

        self.cfg = {}
        self.stringio = {}
        self.warn_count = 0
        self.error_count = 0
        self.name = 'program'
        self.warnings = {self.name: []}
        for name in self.requiredSheets:
            self.warnings[name] = []
        self.errors = {self.name: []}
        for name in self.requiredSheets:
            self.errors[name] = []
        dir_path = os.path.join(input_dir, propname)
        self.cfg['telcfg'] = TelCfgFile(dir_path, logger, file_ext)
        self.cfg['inscfg'] = InsCfgFile(dir_path, logger, file_ext)
        self.cfg['envcfg'] = EnvCfgFile(dir_path, logger, file_ext)
        self.cfg['targets'] = TgtCfgFile(dir_path, logger, file_ext)
        self.cfg['proposal'] = ProposalFile(dir_path, logger, file_ext)
        self.cfg['summary'] = SummaryFile(dir_path, logger, file_ext)

        if file_obj is None:
            # If we didn't get supplied with a file object, that means
            # we need to use the input_dir, file_prefix, file_ext,
            # etc. to locate the input file/directory.
            try:
                self.find_filepath()
            except FileNotFoundError as e:
                if self.file_ext == None or self.file_ext == 'csv':
                    pass
                else:
                    raise FileNotFoundError(e)
        else:
            # If we did get a file object, construct the filename from
            # the proposal name and the file extension.
            self.filepath = '.'.join([propname, file_ext])

        if self.is_excel_file():
            if file_obj:
                # If we were supplied with a file object, just use it.
                self.file_obj = file_obj
            else:
                # If we didn't get a file object, read from the
                # filepath and create a BytesIO object from the file.
                with open(self.filepath, 'rb') as excel_file:
                    self.file_obj = BytesIO(excel_file.read())

            for name, cfg in self.cfg.items():
                cfg.filepath = self.filepath

            self.read_excel_file()

        elif os.path.isdir(dir_path) or file_ext == 'csv':
            for name, cfg in self.cfg.items():
                cfg.find_filepath()
                cfg.read_csv_file()
                self.stringio[name] = cfg.stringio
        else:
            raise UnknownFileFormatError('Program file format %s is unknown for program %s' % (self.file_ext, propname))

        # Check to see if all required sheets were read in
        error_incr = self.checkForRequiredSheets()
        if error_incr > 0:
            return

        # All sheets were read in. Set the configuration objects to
        # have the BytesIO version of the input data
        for name, cfg in self.cfg.items():
            if name in self.requiredSheets:
                cfg.stringio[name] = self.stringio[name]
            else:
                try:
                    cfg.stringio[name] = self.stringio[name]
                except KeyError as e:
                    pass

        # Check to make sure all sheets have the required columns
        error_incr = 0
        for name, cfg in self.cfg.items():
            if name in self.requiredSheets:
                error_incr += cfg.validate_column_names(self)
            else:
                try:
                    error_incr += cfg.validate_column_names(self)
                except KeyError as e:
                    pass
        if error_incr > 0:
            return

        # Check to see if there are any duplicate Code values in any
        # of the sheets
        error_incr = 0
        for name, cfg in self.cfg.items():
            if name in self.requiredSheets:
                error_incr += cfg.checkCodesUnique(self)
            else:
                try:
                    error_incr += cfg.checkCodesUnique(self)
                except KeyError as e:
                    pass
        if error_incr > 0:
            return

        # The "proposal" sheet has values that are used in checking
        # the other sheets, so validate the "proposal" sheet now.
        error_incr = self.cfg['proposal'].validate_datatypes(self)
        if error_incr > 0:
            return
        error_incr = self.cfg['proposal'].validate_data(self)
        if error_incr > 0:
            return

        # Process the "proposal" sheet so that we can use the values
        # to check the other sheets.
        self.cfg['proposal'].process_input()

        # Update the inscfg columnInfo constraints with the
        # constraints from the "proposal" sheet.
        self.cfg['inscfg'].update_constraints(self.cfg['proposal'].proposal_info)

        # Update the envcfg columnInfo constraints with the
        # constraints from the "proposal" sheet.
        self.cfg['envcfg'].update_constraints(self.cfg['proposal'].proposal_info)

        # Now, check the targets, inscfg, envcfg, and telcfg sheets to
        # see if all the input data is valid on them.
        error_incr = 0
        for name in ('targets', 'inscfg', 'envcfg', 'telcfg'):
            error_incr += self.cfg[name].validate_datatypes(self)
        if error_incr > 0:
            return
        for name in ('targets', 'inscfg', 'envcfg', 'telcfg'):
            error_incr += self.cfg[name].validate_data(self, propname)
        if error_incr > 0:
            return

        # We have checked the targets, envcfg, inscfg, and telcfg
        # sheets, so process their input now.
        for name, cfg in self.cfg.items():
            if name != 'proposal':
                if name in self.requiredSheets:
                    cfg.process_input()
                else:
                    try:
                        cfg.process_input()
                    except KeyError as e:
                        pass

        # Start working on the "ob" sheet. First, set up the
        # OBListFile object.
        self.cfg['ob'] = OBListFile(dir_path, logger, propname, propdict,
                                    self.cfg['telcfg'].tel_cfgs,
                                    self.cfg['targets'].tgt_cfgs,
                                    self.cfg['inscfg'].ins_cfgs,
                                    self.cfg['envcfg'].env_cfgs,
                                    file_ext=self.file_ext)

        # Now, either get the "ob" sheet data or read in the ob file.
        if self.is_excel_file():
            self.cfg['ob'].filepath = self.filepath
            self.cfg['ob'].stringio['ob'] = self.stringio['ob']

        elif os.path.isdir(dir_path) or file_ext == 'csv':
            self.cfg['ob'].find_filepath()
            self.cfg['ob'].read_csv_file()
            self.stringio['ob'] = self.cfg['ob'].stringio

        # Check to make sure the "ob" sheet has the required columns
        error_incr += self.cfg['ob'].validate_column_names(self)
        if error_incr > 0:
            return

        # Check to see if there are any duplicate Code values in the
        # "ob" sheet
        error_incr = self.cfg['ob'].checkCodesUnique(self)
        if error_incr > 0:
            return

        # Now, check the "ob" sheet to see if all the input data
        # is valid.
        error_incr = self.cfg['ob'].validate_datatypes(self)
        if error_incr > 0:
            return
        error_incr = self.cfg['ob'].validate_data(self)
        if error_incr > 0:
            return

        # Check the "ob" sheet to see if there are any OB rows that
        # have non-empty calib_tgtcfg but empty calib_inscfg or vice
        # versa.
        self.cfg['ob'].calibCheck(self)

        # Check the "ob" sheet to see if we can find the "Total
        # Required Time" (for S21A onward) or, failing that, the
        # "Total On-src Time" (for S20B and before).
        totalTimeSheetName = 'ob'
        totalTimeName = 'Total Required Time'
        totalTimeValue = self.cfg[totalTimeSheetName].getTotalTime(self, totalTimeName)
        if totalTimeValue is None:
            totalTimeName = 'Total On-src Time'
            totalTimeValue = self.cfg[totalTimeSheetName].getTotalTime(self, totalTimeName)

        # If we didn't find the information we were looking for on the
        # "ob" sheet, check to see if there is a "summary" sheet and
        # use that to get the requested time value.
        if not totalTimeValue:
            totalTimeSheetName = 'summary'
            if totalTimeSheetName in self.stringio:
                totalTimeName = 'Total Accounting Time'
                totalTimeValue = float(self.cfg[totalTimeSheetName].summary_info[totalTimeName])

        # Compare the total required time  to the
        # allocated time on the "proposal" sheet.
        if totalTimeValue:
            self.checkTotalTime(totalTimeSheetName, totalTimeName, totalTimeValue)

        # We have checked the "ob" sheet, so process it now.
        self.cfg['ob'].process_input()

        # Finally, check for orphan codes on the targets, envcfg,
        # inscfg, and telcfg sheets, i.e., codes that are on those
        # sheets but not on the "ob" sheet.
        self.cfg['targets'].checkForOrphanCodes(self, ('tgtcfg', 'calib_tgtcfg'))
        self.cfg['inscfg'].checkForOrphanCodes(self, ('inscfg', 'calib_inscfg'))
        for name in ('envcfg', 'telcfg'):
            self.cfg[name].checkForOrphanCodes(self, (name,))

    def checkForRequiredSheets(self):
        # Check to see if all required sheets were in the file by
        # looking at the contents of our stringio attribute.

        begin_error_count = self.error_count
        for name in self.requiredSheets:
            if name in self.stringio:
                self.logger.debug('Required sheet %s found in file %s' % (name, self.filepath))
            else:
                msg = 'Required sheet %s not found in file %s' % (name, self.filepath)
                self.logger.error(msg)
                self.errors[self.name].append([None, None, msg])
                self.error_count += 1

        return self.error_count - begin_error_count

    def checkTotalTime(self, sheetName, iname, totalTime):

        ph1_allocated_time = float(self.cfg['proposal'].proposal_info['allocated_time'])

        # Round totalTime and ph1_allocated_time to nearest 0.1 second
        # to avoid roundoff errors when comparing the two values.
        totalTime = round(totalTime, 1)
        ph1_allocated_time = round(ph1_allocated_time, 1)

        # Compare totalTime to ph1_allocated_time and report
        # warning if totalTime is greater than ph1_allocated_time
        if totalTime < ph1_allocated_time:
            msg = 'Warning while checking sheet {}: {} of {} seconds is less than the Phase 1 allocated value of {} seconds'.format(sheetName, iname, totalTime, ph1_allocated_time)
            self.logger.warning(msg)
            self.warnings[self.name].append([None, [iname], msg])
            self.warn_count += 1
        elif totalTime == ph1_allocated_time:
            self.logger.debug('Sheet {}: {} of {} seconds is equal to the Phase 1 allocated value of {} seconds and is ok'.format(sheetName, iname, totalTime, ph1_allocated_time))
        else:
            msg = 'Warning while checking sheet {}: {} of {} seconds is greater than the Phase 1 allocated value of {} seconds'.format(sheetName, iname, totalTime, ph1_allocated_time)
            self.logger.warning(msg)
            self.warnings[self.name].append([None, [iname], msg])
            self.warn_count += 1

class SummaryFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        self.name = 'summary'
        self.summary_info = {}
        self.column_map = {
            'quantity': 'quantity',
            'time_(seconds)': 'time_(seconds)',
            }
        self.columnInfo = {
            'quantity':       {'iname': 'Quantity',       'type': str, 'constraint': None, 'prefilled': True, 'required': True},
            'time_(seconds)': {'iname': 'Time (seconds)', 'type': str, 'constraint': None, 'prefilled': True, 'required': True},
            }
        super(SummaryFile, self).__init__(input_dir, 'summary', logger, file_ext)

    def parse_input(self):
        """
        Read the summary information from a CSV file.
        """
        self.queue_file.seek(0)
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments and 'default' line
                if row[0].lower() in ('comment', 'default'):
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                self.summary_info[rec['quantity']] = rec['time_(seconds)']
            except Exception as e:
                raise ValueError("Error reading line %d of summary from file %s: %s" % (
                    lineNum, self.filepath, str(e)))

        self.logger.info(f'summary_info is {self.summary_info}')

class PFS_ProgramFile(QueueFile):
    def __init__(self, input_dir, logger, propname, propdict, file_ext=None, file_obj=None):
        super(PFS_ProgramFile, self).__init__(input_dir, propname, logger, file_ext)
        self.name = 'program'
        self.propdict = propdict
        self.column_map = {
            'ob_code': 'code',
            'obj_id': 'obj_id',
            'ra': 'ra',
            'dec': 'dec',
            'epoch': 'eq',
            'exptime': 'exp_time',
            'priority': 'priority',
            'resolution': 'resolution',
            }
        self.tgt_cfgs = {}
        self.ins_cfgs = {}
        self.obs_info = []

        self.tel_cfgs = {}
        self.env_cfgs = {}

        self.envcfg_default = {'seeing': 10.0,
                               'airmass': 5.0,
                               'transparency': 0.0,
                               'moon_sep': 89.0}

        self.find_filepath()
        if self.file_ext == 'csv':
            self.read_csv_file()
        elif self.is_excel_file():
            with open(self.filepath, 'rb') as excel_file:
                self.file_obj = BytesIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('PFS Program file format %s is unknown' % self.file_ext)

        self.stringio[self.name] = self.stringio[self.file_prefix]

        self.process_input()

    def parse_input(self):
        """
        Parse the PFS program information from the input file.
        """
        self.queue_file.seek(0)
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)

                rec.name = rec.obj_id
                rec.comment = ''
                target = entity.StaticTarget()
                rec.ra = float(rec.ra) / 15.0
                code = target.import_record(rec)

                self.tgt_cfgs[code] = target

                inscfg = entity.PFSConfiguration(exp_time=rec.exp_time, resolution=rec.resolution)
                self.ins_cfgs[code] = inscfg

                telcfg = entity.TelescopeConfiguration(focus='PFS')
                self.tel_cfgs[code] = telcfg
                envcfg = entity.EnvironmentConfiguration(seeing=self.envcfg_default['seeing'],
                                                         airmass=self.envcfg_default['airmass'],
                                                         transparency=self.envcfg_default['transparency'],
                                                         moon_sep=self.envcfg_default['moon_sep'],
                                                         )
                self.env_cfgs[code] = envcfg

                self.obs_info.append(entity.PFS_OB(id=code, program=self.propdict[self.file_prefix], target=target, inscfg=inscfg, telcfg=telcfg, envcfg=envcfg, total_time=float(rec.exp_time), acct_time=float(rec.exp_time)))

            except Exception as e:
                raise ValueError("Error reading line %d of PFS program: %s" % (
                    lineNum, str(e)))

class PPCFile(QueueFile):
    def __init__(self, input_dir, logger, propname, propdict,
                 file_ext=None):
        """Read in a PFS Pointing Center file.
        """
        # obs_info is the list of OB objects that will be used by the
        # observing block scheduling functions.
        self.name = propname
        self.obs_info = []
        self.proposal = propname.upper()
        self.propdict = propdict
        self.column_map = {
            'ppc_code': 'ob_code',
            'ppc_ra': 'ra',
            'ppc_dec': 'dec',
            'ppc_equinox': 'eq',
            'ppc_pa': 'pa_deg',
            'ppc_resolution': 'resolution',
            'ppc_exptime': 'exp_time',
            'ppc_totaltime': 'total_time',
            'ppc_priority': 'priority',
            'ppc_comment': 'comment',
            }
        super(PPCFile, self).__init__(input_dir, propname, logger,
                                      file_ext)

        self.find_filepath()
        if self.file_ext in ['csv', 'ecsv']:
            self.read_csv_file()
        elif self.is_excel_file():
            with open(self.filepath, 'rb') as excel_file:
                self.file_obj = BytesIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('PPC file format %s is unknown' % self.file_ext)
        self.process_input()

    def parse_input(self):
        """
        Parse the programs from the input file.
        """
        self.queue_file.seek(0)
        self.obs_info = []
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                first_col_content = row[0].strip()
                if first_col_content.lower() == 'comment' or \
                   (len(first_col_content) > 0 and first_col_content[0] == '#'):
                    continue
                # skip blank lines
                if len(first_col_content) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames, self.column_map)

                ob_code = rec.ob_code.strip()

                program = self.propdict[self.proposal]

                priority = 1.0
                if rec.priority != None:
                    priority = float(rec.priority)

                # PPP provides exp_time, total_time in sec
                exp_time = float(rec.exp_time)
                total_time = float(rec.total_time)

                comment = ''
                if rec.has_key('comment'):
                    comment = rec.comment.strip()
                tgtcfg = entity.StaticTarget()
                # should we add a "name" column for the field center?
                rec.name = ob_code
                tgtcfg.import_record(rec)
                # fixed telescope configuration for PPC scheduling
                telcfg = entity.TelescopeConfiguration(focus='p-opt2',
                                                       dome='open',
                                                       min_rot_deg=-174.0,
                                                       max_rot_deg=+174.0)
                inscfg = entity.PPCConfiguration(exp_time=exp_time,
                                                 resolution=rec.resolution.lower(),
                                                 pa=float(rec.pa_deg))
                # right now there are no configuration limitations
                envcfg = entity.EnvironmentConfiguration(seeing=999.0,
                                                         airmass=2.0,
                                                         transparency=0.0,
                                                         moon_sep=0.0)
                ob = entity.PPC_OB(id=ob_code,
                                   program=program,
                                   target=tgtcfg,
                                   inscfg=inscfg,
                                   envcfg=envcfg,
                                   telcfg=telcfg,
                                   priority=priority,
                                   total_time=total_time,
                                   acct_time=exp_time,
                                   comment=comment)
                self.obs_info.append(ob)

            except Exception as e:
                raise ValueError("Error reading line %d of ppc: %s" % (
                    lineNum, str(e)))


    def update_table(self, tbl_dct, parse_flag=False):
        """Update items in the internal table representation (self.rows).
        """

        for row_key, col_dct in tbl_dct.items():

            row_key = row_key.upper()
            # locate row index for this row_key
            # TODO: make more efficient!
            found = False
            for row_idx in range(0, len(self.rows)):
                if self.rows[row_idx]['ob_code'].upper() == row_key:
                    found = True
                    break

            if not found:
                raise ValueError(f"Can't find entry for row_key={row_key}")

            for col_key, col_val in col_dct.items():
                # locate column header for this col_key
                # TODO: make more efficient!
                found = False
                for col_hdr, ent_field in self.column_map.items():
                    if ent_field == col_key:
                        found = True
                        break

                if not found:
                    raise ValueError(f"Can't find entry for col_key={col_key}")

                # update the cell in the table representation
                self.rows[row_idx][col_hdr] = col_val

        if parse_flag:
            self.parse()


register_matplotlib_converters()

#END
