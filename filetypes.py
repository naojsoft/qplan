#
# filetypes.py -- CSV file interfaces
#
# Russell Kackley (rkackley@naoj.org)
# Eric Jeschke (eric@naoj.org)
#
import os
import pandas as pd
import csv
import string
import StringIO
import datetime
import re

import entity
from ginga.misc import Bunch

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

    def __init__(self, input_dir, file_prefix, logger, file_ext=None, **parse_kwdargs):
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
            with open(self.filepath, 'rb') as f:
                self.stringio[self.file_prefix] = StringIO.StringIO(f.read())
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
                    self.stringio[name] = StringIO.StringIO()
                    self.df[name].to_csv(self.stringio[name], index=False)
                    self.stringio[name].seek(0)
        else:
            raise IOError('File path not defined for file prefix %s' % self.file_prefix)

    def is_excel_file(self):
        if self.file_ext in self.excel_ext:
            return True
        else:
            return False

    def process_input(self, name):

        # Read and save the first line, which should have the column
        # titles.
        self.stringio[name].seek(0)
        self.queue_file = self.stringio[name]
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
        # We are done with the StringIO object, so close it.
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
        # Override in subclass
        pass

    def update(self, row, colHeader, value, parse_flag):
        # User has changed a value in the table, so update our "rows"
        # attribute, recreate the StringIO object, and parse the input
        # again.
        self.logger.debug('QueueFile.update row %d colHeader %s value %s' % (row, colHeader, value))
        self.rows[row][colHeader] = value

        # Use the CSV "writer" classes to create a new version of the
        # StringIO object from our "rows" attribute.
        if parse_flag:
            self.parse()

    def parse(self):
        # Create a StringIO.StringIO object and write our columnNames
        # and rows attributes into that object. This gives us an
        # object that looks like a disk file so we can parse the data.
        self.queue_file = StringIO.StringIO()
        writer = csv.writer(self.queue_file, **self.fmtparams)
        writer.writerow(self.columnNames)
        writer = csv.DictWriter(self.queue_file, self.columnNames, **self.fmtparams)
        for row in self.rows:
            writer.writerow(row)

        # Parse the input data from the StringIO.StringIO object
        try:
            self.parse_input()

        except Exception as e:
            self.logger.error("Error reparsing input: %s" % (str(e)))

        # We are done with the StringIO object, so close it.
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
            key = colname.strip().lower().replace(' ', '_')
            # get attr key
            if not key in column_map:
                #self.logger.warn("No column->record map entry for column '%s' (%s); skipping..." % (colname, key))
                continue
            attrkey = column_map[key]
            rec[attrkey] = row[i]
        return rec

class ScheduleFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        # schedule_info is the list of tuples that will be used by the
        # observing block scheduling functions.
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
            'note': 'note',
            }
        super(ScheduleFile, self).__init__(input_dir, 'schedule', logger, file_ext)
        self.find_filepath()
        if self.file_ext == 'csv':
            self.read_csv_file()
        elif self.is_excel_file:
            with open(self.filepath, 'r') as excel_file:
                self.file_obj = StringIO.StringIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('File format %s is unknown' % self.file_ext)
        self.process_input('schedule')

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

            filters = list(map(string.strip, rec.filters.lower().split(',')))
            instruments = list(map(string.strip,
                                   rec.instruments.upper().split(',')))
            seeing = float(rec.seeing)
            categories = rec.categories.replace(' ', '').lower().split(',')
            transparency = float(rec.transparency)
            dome = rec.dome.lower()

            # TEMP: skip non-OPEN categories
            if not 'open' in categories:
                continue

            # data record of current conditions
            # All OBs for this schedule slot should end up pointing to this
            # static record
            data = Bunch.Bunch(filters=filters,
                               seeing=seeing, transparency=transparency,
                               dome=dome, categories=categories,
                               instruments=instruments)

            rec2 = Bunch.Bunch(date=rec.date, starttime=rec.starttime,
                               stoptime=rec.stoptime,
                               #categories=categories,
                               note=rec.note,
                               data=data)
            self.schedule_info.append(rec2)


class ProgramsFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
        # programs_info is the dictionary of Program objects that will
        # be used by the observing block scheduling functions.
        self.programs_info = {}
        self.column_map = {
            'proposal': 'proposal',
            'propid': 'propid',
            'rank': 'rank',
            'category': 'category',
            'instruments': 'instruments',
            'grade': 'grade',
            'hours': 'hours',
            'partner': 'partner',
            'skip': 'skip',
            }
        super(ProgramsFile, self).__init__(input_dir, 'programs', logger, file_ext)
        self.find_filepath()
        if self.file_ext == 'csv':
            self.read_csv_file()
        elif self.is_excel_file:
            with open(self.filepath, 'r') as excel_file:
                self.file_obj = StringIO.StringIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('File format %s is unknown' % self.file_ext)
        self.process_input('programs')

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
                if rec.skip.strip() != '':
                    continue

                key = rec.proposal.upper()
                pgm = entity.Program(key, propid=rec.propid,
                                     rank=float(rec.rank),
                                     grade=rec.grade.upper(),
                                     partner=rec.partner,
                                     category=rec.category,
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


class WeightsFile(QueueFile):

    def __init__(self, input_dir, logger, file_ext=None):

        self.weights = Bunch.Bunch()
        self.column_map = {
            'slew': 'w_slew',
            'delay': 'w_delay',
            'filter': 'w_filterchange',
            'rank': 'w_rank',
            'priority': 'w_priority',
            }
        super(WeightsFile, self).__init__(input_dir, 'weights', logger, file_ext)
        self.find_filepath()
        if self.file_ext == 'csv':
            self.read_csv_file()
        elif self.is_excel_file:
            with open(self.filepath, 'r') as excel_file:
                self.file_obj = StringIO.StringIO(excel_file.read())
            self.read_excel_file()
        else:
            raise UnknownFileFormatError('File format %s is unknown' % self.file_ext)
        self.process_input('weights')

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


class TelCfgFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
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
            'code':         {'iname': 'Code', 'type': str, 'constraint': None},
            'foci':         {'iname': 'Foci', 'type': str, 'constraint': "value in %s" % self.foci},
            'dome':         {'iname': 'Dome', 'type': str, 'constraint': "value in %s" % self.dome_states},
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
        self.env_cfgs = {}
        self.column_map = {
            'code': 'code',
            'seeing': 'seeing',
            'airmass': 'airmass',
            'moon': 'moon',
            'moon_sep': 'moon_sep',
            #'sky': 'sky',
            'transparency': 'transparency',
            'comment': 'comment',
            }
        self.moon_states = "('dark', 'gray', 'any')".upper()
        self.columnInfo = {
            'code':         {'iname': 'Code',         'type': str,   'constraint': None},
            'seeing':       {'iname': 'Seeing',       'type': float, 'constraint': "value > 0.0"},
            'airmass':      {'iname': 'Airmass',      'type': float, 'constraint': "value >= 1.0"},
            'moon':         {'iname': 'Moon',         'type': str,   'constraint': "value in %s" % self.moon_states},
            'moon_sep':     {'iname': 'Moon Sep',     'type': float, 'constraint': None},
            'transparency': {'iname': 'Transparency', 'type': float, 'constraint': "value >= 0.0 and value <= 1.0"},
            }

        super(EnvCfgFile, self).__init__(input_dir, 'envcfg', logger, file_ext)

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


class TgtCfgFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
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
            'code':         {'iname': 'Code',        'type': str, 'constraint': None},
            'target_name':  {'iname': 'Target Name', 'type': str, 'constraint': None},
            'ra':           {'iname': 'RA',          'type': str, 'constraint': self.parseRA},
            'dec':          {'iname': 'DEC',         'type': str, 'constraint': self.parseDec},
            'equinox':      {'iname': 'Equinox',     'type': str, 'constraint': "value in ('J2000', 'B1950')"},
            'sdss_ra':      {'iname': 'SDSS RA',     'type': str, 'constraint': self.parseRA},
            'sdss_dec':     {'iname': 'SDSS DEC',    'type': str, 'constraint': self.parseDec},
            }
        super(TgtCfgFile, self).__init__(input_dir, 'targets', logger, file_ext)

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
        d = float(d)
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

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                target = entity.StaticTarget()
                code = target.import_record(rec)

                # update existing old record if it exists
                # since OBs may be pointing to it
                if code in old_cfgs:
                    new_cfg = target
                    target = old_cfgs[code]
                    target.__dict__.update(new_cfg.__dict__)

                self.tgt_cfgs[code] = target

            except Exception as e:
                raise ValueError("Error reading line %d of oblist from file %s: %s" % (
                    lineNum, self.filepath, str(e)))


class InsCfgFile(QueueFile):
    def __init__(self, input_dir, logger, file_ext=None):
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
                        'on-src_time': 'on-src_time',
                        'total_time': 'total_time',
                        'comment': 'comment',
                        }),
            'FOCAS': (entity.FOCASConfiguration,
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
                        'dither_ra': 'dither_ra',
                        'dither_dec': 'dither_dec',
                        'dither_theta': 'dither_theta',
                        'binning': 'binning',
                        'comment': 'comment',
                        }),
            'SPCAM': (entity.SPCAMConfiguration,
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
                        'comment': 'comment',
                        }),
            }

        self.HSC_filters =   "('g', 'r', 'i', 'z', 'Y', 'NB921', 'NB816', 'NB515')".upper()
        self.FOCAS_filters = "('U', 'B', 'V', 'R', 'I', 'N373', 'N386', 'N487', 'N502', 'N512', 'N642', 'N658', 'N670')".upper()
        self.SPCAM_filters = "('B', 'V', 'Rc', 'Ic', 'g\'', 'r\'', 'i\'', 'z\'', 'Y', 'NA656', 'NB711', 'NB816', 'NB921')".upper()

        self.HSC_modes = "('imaging',)".upper()
        self.FOCAS_modes = "('imaging', 'spectroscopy')".upper()
        self.SPCAM_modes = "('imaging',)".upper()

        self.dither_constr = "value in ('1', '5', 'N')"
        self.guiding_constr = "value in ('Y','N')"
        self.columnInfo = {
            'HSC': {
            'code':         {'iname': 'Code',       'type': str,   'constraint': None},
            'instrument':   {'iname': 'Instrument', 'type': str,   'constraint': "value == 'HSC'"},
            'mode':         {'iname': 'Mode',       'type': str,   'constraint': "value in %s" % self.HSC_modes},
            'filter':       {'iname': 'Filter',     'type': str,   'constraint': "value in %s" % self.HSC_filters},
            'exp_time':     {'iname': 'Exp Time',   'type': float, 'constraint': "value > 0.0"},
            'num_exp':      {'iname': 'Num Exp',    'type': int,   'constraint': "value > 0"},
            'dither':       {'iname': 'Dither',     'type': str,   'constraint': self.dither_constr},
            'guiding':      {'iname': 'Guiding',    'type': str,   'constraint': self.guiding_constr},
            'pa':           {'iname': 'PA',         'type': float, 'constraint': None},
            'offset_ra':    {'iname': 'Offset RA',  'type': float, 'constraint': None},
            'offset_dec':   {'iname': 'Offset DEC', 'type': float, 'constraint': None},
            'dith1':        {'iname': 'Dith1',      'type': float, 'constraint': None},
            'dith2':        {'iname': 'Dith2',      'type': float, 'constraint': None},
            'skip':         {'iname': 'Skip',       'type': int,   'constraint': None},
            'stop':         {'iname': 'Stop',       'type': int,   'constraint': None},
            'on-src_time':  {'iname': 'On-src Time','type': float, 'constraint': None},
            'total_time':   {'iname': 'Total Time', 'type': float, 'constraint': None},
            },
            'FOCAS': {
            'code':         {'iname': 'Code',        'type': str,   'constraint': None},
            'instrument':   {'iname': 'Instrument',  'type': str,   'constraint': "value == 'FOCAS'"},
            'mode':         {'iname': 'Mode',        'type': str,   'constraint': "value in %s" % self.FOCAS_modes},
            'filter':       {'iname': 'Filter',      'type': str,   'constraint': "value in %s" % self.FOCAS_filters},
            'exp_time':     {'iname': 'Exp Time',    'type': float, 'constraint': "value > 0.0"},
            'num_exp':      {'iname': 'Num Exp',     'type': int,   'constraint': "value > 0"},
            'dither':       {'iname': 'Dither',      'type': str,   'constraint': self.dither_constr},
            'guiding':      {'iname': 'Guiding',     'type': str,   'constraint': self.guiding_constr},
            'pa':           {'iname': 'PA',          'type': float, 'constraint': None},
            'offset_ra':    {'iname': 'Offset RA',   'type': float, 'constraint': None},
            'offset_dec':   {'iname': 'Offset DEC',  'type': float, 'constraint': None},
            'dither_ra':    {'iname': 'Dither RA',   'type': float, 'constraint': None},
            'dither_dec':   {'iname': 'Dither DEC',  'type': float, 'constraint': None},
            'dither_theta': {'iname': 'Dither Theta','type': float, 'constraint': None},
            'binning':      {'iname': 'Binning',     'type': str,   'constraint': "x in ('1x1',)"},
            },
            'SPCAM': {
            'code':         {'iname': 'Code',       'type': str,   'constraint': None},
            'instrument':   {'iname': 'Instrument', 'type': str,   'constraint': "value == 'SPCAM'"},
            'mode':         {'iname': 'Mode',       'type': str,   'constraint': "value in %s" % self.SPCAM_modes},
            'filter':       {'iname': 'Filter',     'type': str,   'constraint': "value in %s" % self.SPCAM_filters},
            'exp_time':     {'iname': 'Exp Time',   'type': float, 'constraint': "value > 0.0"},
            'num_exp':      {'iname': 'Num Exp',    'type': int,   'constraint': "value > 0"},
            'dither':       {'iname': 'Dither',     'type': str,   'constraint': self.dither_constr},
            'guiding':      {'iname': 'Guiding',    'type': str,   'constraint': self.guiding_constr},
            'pa':           {'iname': 'PA',         'type': float, 'constraint': None},
            'offset_ra':    {'iname': 'Offset RA',  'type': float, 'constraint': None},
            'offset_dec':   {'iname': 'Offset DEC', 'type': float, 'constraint': None},
            'dith1':        {'iname': 'Dith1',      'type': float, 'constraint': None},
            'dith2':        {'iname': 'Dith2',      'type': float, 'constraint': None},
            },
            }
        self.max_onsource_time_hrs = 2.0 # hours
        super(InsCfgFile, self).__init__(input_dir, 'inscfg', logger, file_ext)
        self.excel_converters = {'Num Exp': lambda x: int(x) if x else '',
                                 'Dither':  lambda x: str(x) if x else ''}

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

                # skip comments
                if row[0].lower() == 'comment':
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



class OBListFile(QueueFile):
    def __init__(self, input_dir, logger, propname, propdict,
                 telcfgs, tgtcfgs, inscfgs, envcfgs, file_ext=None):
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
            'id': 'id',
            'code': 'code',
            'tgtcfg': 'tgt_code',
            'inscfg': 'ins_code',
            'telcfg': 'tel_code',
            'envcfg': 'env_code',
            'priority': 'priority',
            'on-src_time': 'on-src_time',
            'total_time': 'total_time',
            'comment': 'comment',
            }
        self.columnInfo = {
            'code':       {'iname': 'Code', 'type': str,   'constraint': None},
            'tgtcfg':     {'iname': 'tgtcfg', 'type': str,   'constraint': self.tgtcfgCheck},
            'inscfg':     {'iname': 'inscfg', 'type': str,   'constraint': self.inscfgCheck},
            'telcfg':     {'iname': 'telcfg', 'type': str,   'constraint': self.telcfgCheck},
            'envcfg':     {'iname': 'envcfg', 'type': str,   'constraint': self.envcfgCheck},
            'priority':   {'iname': 'Priority', 'type': float, 'constraint': None},
            'on-src_time':{'iname': 'On-src Time','type': float, 'constraint': None},
            'total_time': {'iname': 'Total Time', 'type': float, 'constraint': None},
            }
        super(OBListFile, self).__init__(input_dir, 'ob', logger, file_ext=file_ext)

    def tgtcfgCheck(self, tgtcfg, tgt_config):
        return tgtcfg in tgt_config.tgt_cfgs

    def inscfgCheck(self, inscfg, ins_config):
        return inscfg in ins_config.ins_cfgs

    def telcfgCheck(self, telcfg, tel_config):
        return telcfg in tel_config.tel_cfgs

    def envcfgCheck(self, envcfg, env_config):
        return envcfg in env_config.env_cfgs

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
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row, self.columnNames,
                                     self.column_map)
                code = rec.code.strip()

                program = self.propdict[self.proposal]
                envcfg = self.envcfgs[rec.env_code.strip()]
                telcfg = self.telcfgs[rec.tel_code.strip()]
                tgtcfg = self.tgtcfgs[rec.tgt_code.strip()]
                inscfg = self.inscfgs[rec.ins_code.strip()]

                priority = 1.0
                if rec.priority != None:
                    priority = float(rec.priority)

                ob = entity.OB(program=program,
                               target=tgtcfg,
                               inscfg=inscfg,
                               envcfg=envcfg,
                               telcfg=telcfg,
                               priority=priority,
                               name=code,
                               total_time=float(rec.total_time))
                self.obs_info.append(ob)

            except Exception as e:
                raise ValueError("Error reading line %d of oblist from file %s: %s" % (
                    lineNum, self.filepath, str(e)))

class ProgramFile(QueueFile):
    def __init__(self, input_dir, logger, propname, propdict, file_ext=None, file_obj=None):
        super(ProgramFile, self).__init__(input_dir, propname, logger, file_ext)
        self.requiredSheets = ('telcfg', 'inscfg', 'envcfg', 'targets', 'ob')

        self.cfg = {}
        self.warn_count = 0
        self.error_count = 0
        self.warnings = {}
        for name in self.requiredSheets:
            self.warnings[name] = []
        self.errors = {}
        for name in self.requiredSheets:
            self.errors[name] = []
        dir_path = os.path.join(input_dir, propname)
        self.cfg['telcfg'] = TelCfgFile(dir_path, logger, file_ext)
        self.cfg['inscfg'] = InsCfgFile(dir_path, logger, file_ext)
        self.cfg['envcfg'] = EnvCfgFile(dir_path, logger, file_ext)
        self.cfg['targets'] = TgtCfgFile(dir_path, logger, file_ext)

        if file_obj is None:
            # If we didn't get supplied with a file object, that means
            # we need to use the input_dir, file_prefix, file_ext,
            # etc. to locate the input file/directory.
            try:
                self.find_filepath()
            except FileNotFoundError, e:
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
                # filepath and create a StringIO object from the file.
                with open(self.filepath, 'r') as excel_file:
                    self.file_obj = StringIO.StringIO(excel_file.read())

            for name, cfg in self.cfg.iteritems():
                cfg.filepath = self.filepath

            self.read_excel_file()

            error_incr = self.validate()

            if error_incr > 0:
                return

            for name, cfg in self.cfg.iteritems():
                cfg.stringio[name] = self.stringio[name]
                cfg.process_input(name)

            self.cfg['ob'] = OBListFile(dir_path, logger, propname, propdict,
                                        self.cfg['telcfg'].tel_cfgs,
                                        self.cfg['targets'].tgt_cfgs,
                                        self.cfg['inscfg'].ins_cfgs,
                                        self.cfg['envcfg'].env_cfgs,
                                        file_ext=file_ext)
            self.cfg['ob'].filepath = self.filepath
            error_incr = self.validate_column_names('ob')
            if error_incr > 0:
                return
            error_incr = self.validate_data('ob')
            if error_incr > 0:
                return
            self.cfg['ob'].stringio['ob'] = self.stringio['ob']
            self.cfg['ob'].process_input('ob')

        elif os.path.isdir(dir_path) or file_ext == 'csv':

            for name, cfg in self.cfg.iteritems():
                cfg.find_filepath()
                cfg.read_csv_file()
                self.stringio[name] = cfg.stringio[name]
                error_incr = self.validate_column_names(name)
                if error_incr > 0:
                    continue
                error_incr = self.validate_data(name)
                cfg.process_input(name)

            if self.error_count > 0:
                return

            self.cfg['ob'] = OBListFile(dir_path, logger, propname, propdict,
                                        self.cfg['telcfg'].tel_cfgs,
                                        self.cfg['targets'].tgt_cfgs,
                                        self.cfg['inscfg'].ins_cfgs,
                                        self.cfg['envcfg'].env_cfgs,
                                        file_ext=file_ext)
            self.cfg['ob'].find_filepath()
            self.cfg['ob'].read_csv_file()
            self.stringio['ob'] = self.cfg['ob'].stringio['ob']
            error_incr = self.validate_column_names('ob')
            if error_incr > 0:
                return
            error_incr = self.validate_data('ob')
            if error_incr > 0:
                return
            self.cfg['ob'].process_input('ob')

        else:
            raise UnknownFileFormatError('File format %s is unknown' % self.file_ext)

    def validate(self):

        begin_error_count = self.error_count
        # Check to see if all required sheets are in the file
        for name in self.requiredSheets:
            if name in self.stringio:
                self.logger.debug('Required sheet %s found in file %s' % (name, self.filepath))
            else:
                msg = 'Required sheet %s not found in file %s' % (name, self.filepath)
                self.logger.error(msg)
                self.errors[name].append([None, None, msg])
                self.error_count += 1

        if self.error_count > begin_error_count:
            return self.error_count - begin_error_count

        # Check to see if all sheets have the required columns and
        # that the contents of the columns can be parsed and meet the
        # constraint(s), if any.
        for name in self.cfg:
            self.validate_column_names(name)
            self.validate_data(name)

        return self.error_count - begin_error_count

    def get_insname(self):
        # Access the inscfg information to determine the instrument
        # name. Hopefully, the first row has the column names and the
        # second row is parseable so that we can get the instrument
        # name.
        self.stringio['inscfg'].seek(0)
        self.queue_file = self.stringio['inscfg']
        reader = csv.reader(self.queue_file, **self.fmtparams)
        column_names = next(reader)
        row = next(reader)
        rec = self.parse_row(row, column_names, self.cfg['inscfg'].column_map)
        insname = rec.insname
        return insname

    def validate_column_names(self, name):

        begin_error_count = self.error_count

        # Check to make sure that the supplied sheet has the required
        # column names in the first row. First, get the column names
        # from the first row.
        self.stringio[name].seek(0)
        self.queue_file = self.stringio[name]
        reader = csv.reader(self.queue_file, **self.fmtparams)
        column_names = next(reader)

        # For the inscfg sheet, we need to figure out the instrument
        # name because each instrument has a different set of columns.
        if name == 'inscfg':
            insname = self.get_insname()
            columnInfo = self.cfg[name].columnInfo[insname]
            self.stringio[name].seek(0)
            next(reader)
        else:
            columnInfo = self.cfg[name].columnInfo

        # Iterate through the list of required columns to make sure
        # they are all there.
        for col_name in columnInfo:
            if columnInfo[col_name]['iname'] in column_names:
                self.logger.debug('Column name %s found in sheet %s' % (columnInfo[col_name]['iname'], name))
            else:
                msg = 'Required column %s not found in sheet %s' % (columnInfo[col_name]['iname'], name)
                self.logger.error(msg)
                self.errors[name].append([1, [columnInfo[col_name]['iname']], msg])
                self.error_count += 1

            # Warn the user if there is a column with a name that
            # starts with one of the expected names, but then has
            # appended to the name a ".1", ".2", etc. This means that
            # there was a duplicate column name in the spreadsheet and
            # Pandas appended a sequence number to make the subsequent
            # columns have unique names.
            pattern = columnInfo[col_name]['iname'] + '\.\d+'
            dup_count = 0
            for cname in column_names:
                if re.match(pattern, cname):
                    dup_count += 1
            if dup_count > 0:
                msg = '%d duplicate %s column(s) found in sheet %s' % (dup_count, columnInfo[col_name]['iname'], name)
                self.logger.warn(msg)
                self.warnings[name].append([1, [columnInfo[col_name]['iname']], msg])
                self.warn_count += 1

        return self.error_count - begin_error_count

    def validate_data(self, name):

        begin_error_count = self.error_count

        # Check to make sure that all the data in the sheet is valid
        # and meets the constraints.
        self.stringio[name].seek(0)
        self.queue_file = self.stringio[name]
        reader = csv.reader(self.queue_file, **self.fmtparams)
        column_names = next(reader)

        # For the inscfg sheet, we need to figure out the instrument
        # name because each instrument has a different set of columns.
        if name == 'inscfg':
            insname = self.get_insname()
            columnInfo = self.cfg[name].columnInfo[insname]
            column_map = self.cfg[name].configs[insname][1]
            self.stringio[name].seek(0)
            next(reader)
        else:
            columnInfo = self.cfg[name].columnInfo
            column_map = self.cfg[name].column_map

        # Iterate through all the rows in the sheet.
        codes = {}
        for i, row in enumerate(reader):
            self.logger.debug('Sheet %s Line %d Row is %s' % (name, i+1, row))
            row_num = i + 1
            rec = self.parse_row(row, column_names, column_map)
            self.validate_row(name, codes, rec, row_num, columnInfo, column_map)

        return self.error_count - begin_error_count

    def validate_row(self, name, codes, rec, row_num, columnInfo, column_map):

        begin_error_count = self.error_count

        # Check the data in the supplied row to make sure it meets the
        # constraints specified in columnInfo.
        if rec.code == '':
            # We don't care about lines with no entry in the Code column
            self.logger.debug('Skipping line %d with blank Code entry in sheet %s' % (row_num, name))
        else:
            # First, check to make sure the Code is unique
            if rec.code in codes:
                msg = "Warning while checking line %d, column Code of sheet %s: Duplicate code value identified: %s" % (row_num, name, rec.code)
                self.logger.warn(msg)
                self.warnings[name].append([row_num, [columnInfo['code']['iname']], msg])
                self.warn_count += 1
            else:
                codes[rec.code] = True

            # A special check on the "inscfg" sheet: compute on-source
            # time and check to see if it is less than the recommended
            # limit (currently two hours). Eventually, the on-source
            # time might be available from the "inscfg" sheet, but,
            # for now, compute the on-source time here.
            if name == 'inscfg':
                try:
                    onsource_time_hrs = (float(rec.exp_time) * int(rec.num_exp)) / 3600.0
                    if onsource_time_hrs <= self.cfg['inscfg'].max_onsource_time_hrs:
                        self.logger.debug('Line %d of sheet %s: onsource time of %.1f hours is less than recommended maximum value of %.1f hours' % (row_num, name, onsource_time_hrs, self.cfg['inscfg'].max_onsource_time_hrs))
                    else:
                        msg = 'Warning while checking line %d of sheet %s: onsource time of %.1f hours exceeds recommended maximum of %.1f hours' % (row_num, name, onsource_time_hrs, self.cfg['inscfg'].max_onsource_time_hrs)
                        self.logger.warn(msg)
                        self.warnings[name].append([row_num, [columnInfo['exp_time']['iname'], columnInfo['num_exp']['iname']], msg])
                        self.warn_count += 1
                except ValueError:
                    msg = "Warning while checking line %d of sheet %s: Unable to compute on-source time. Cannot parse exp_time %s and/or num_exp %s" % (row_num, name, rec.exp_time, rec.num_exp)
                    self.logger.warn(msg)
                    self.warnings[name].append([row_num, [columnInfo['exp_time']['iname'], columnInfo['num_exp']['iname']], msg])
                    self.warn_count += 1

            # Iterate through all the columns and check constraints, if any.
            for col_name, info in columnInfo.iteritems():
                rec_name = column_map[col_name]
                # Check to see if the record has the desired
                # column. If not, there is not much we can do, so skip
                # over this record. The fact that a column is missing
                # or mis-labeled will have already been reported by
                # the validate_column_names method.
                try:
                    str_val = rec[rec_name]
                except KeyError, e:
                    continue
                # First, see if we can coerce the string value into
                # the desired datatype.
                try:
                    val = info['type'](str_val)
                except ValueError, e:
                    msg = "Error evaluating line %d, column %s of sheet %s: cannot evaluate '%s' as %s" % (row_num, col_name, name, str_val, info['type'])
                    self.logger.error(msg)
                    self.errors[name].append([row_num, [columnInfo[col_name]['iname']], msg])
                    self.error_count += 1
                    continue
                # If there is a constraint, check the value to see if
                # it meets the constraint requirement.
                if info['constraint']:
                    # The first test checks the configuration
                    # reference columns in the "ob" sheet.
                    if col_name in ('tgtcfg', 'inscfg', 'telcfg', 'envcfg'):
                        if col_name in ('inscfg', 'telcfg', 'envcfg'):
                            cfg_name = col_name
                        else:
                            cfg_name = 'targets'
                        if info['constraint'](val, self.cfg[cfg_name]):
                            self.logger.debug('Line %d, column %s of sheet %s: found %s %s in %s sheet' % (row_num, col_name, name, col_name, val, cfg_name))
                        else:
                            msg = 'Error while checking line %d, column %s of sheet %s: %s %s does not appear in %s sheet' % (row_num, col_name, name, col_name, val, cfg_name)
                            self.logger.error(msg)
                            self.errors[name].append([row_num, [columnInfo[col_name]['iname']], msg])
                            self.error_count += 1

                    elif col_name in ('ra', 'dec', 'sdss_ra', 'sdss_dec'):
                        # This is a special check of the RA/Dec
                        # values.
                        if info['constraint'](val):
                            self.logger.debug('Line %d, column %s of sheet %s: %s %s is ok' % (row_num, col_name, name, col_name, val))
                        else:
                            msg = 'Warning while checking line %d, column %s of sheet %s: %s %s is not valid' % (row_num, col_name, name, col_name, val)
                            self.logger.warn(msg)
                            self.warnings[name].append([row_num, [columnInfo[col_name]['iname']], msg])
                            self.warn_count += 1

                    else:
                        # Finally, the generic constraint check as
                        # defined in columnInfo.
                        l = lambda(value): eval(info['constraint'])
                        # Try to convert supplied value to upper-case
                        # to make it easier to check constraints for
                        # string values. If the conversion fails with
                        # an AttributeError exception, it is probably
                        # because the value is not a string, so ignore
                        # the exception.
                        try:
                            val = val.upper()
                        except AttributeError:
                            pass
                        if l(val):
                            self.logger.debug('Line %d, column %s of sheet %s: %s meets the constraint of %s' % (row_num, col_name, name, val, info['constraint']))
                        else:
                            msg = 'Warning while checking line %d, column %s of sheet %s: %s does not meet the constraint of %s' % (row_num, col_name, name, val, info['constraint'])
                            self.logger.warn(msg)
                            self.warnings[name].append([row_num, [columnInfo[col_name]['iname']], msg])
                            self.warn_count += 1

        return self.error_count - begin_error_count
#END
