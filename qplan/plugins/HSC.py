#
# HSC.py -- OB converter for HSC instrument
#
#  Eric Jeschke (eric@naoj.org)
#
import time

from ..q2ope import BaseConverter

# the set of OPE friendly characters--for mangling target names
ope_friendly_chars = []
letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ope_friendly_chars.extend(list(letters))
ope_friendly_chars.extend(list(letters.lower()))
ope_friendly_chars.extend(list("0123456789_"))
ope_friendly_chars = set(ope_friendly_chars)

# the mapping of HSC filters
filternames = dict(G="HSC-g", R="HSC-r2", R2="HSC-r2",
                   I="HSC-i2", I2="HSC-i2",
                   Z="HSC-z", Y="HSC-Y")

# appropriate combinations of (GOODMAG, AG_EXP) by filter are:
ag_exp_info = {
    'g': dict(goodmag=13.5, ag_exp=0.2),
    'i': dict(goodmag=14.0, ag_exp=0.2),
    'i2': dict(goodmag=14.0, ag_exp=0.2),
    'y': dict(goodmag=14.0, ag_exp=0.3),
    'r': dict(goodmag=14.5, ag_exp=0.2),
    'r2': dict(goodmag=14.5, ag_exp=0.2),
    'z': dict(goodmag=13.0, ag_exp=0.3),
    'nb515': dict(goodmag=12.5, ag_exp=0.5),
    'nb921': dict(goodmag=12.5, ag_exp=0.5),
    'nb387': dict(goodmag=11.0, ag_exp=10.0),
    }

class Converter(BaseConverter):

    def _setup_target(self, d, ob):

        funky_ra = self.ra_to_funky(ob.target.ra)
        funky_dec = self.dec_to_funky(ob.target.dec)

        autoguide = False
        d.update(dict(guidestr=''))
        if ob.inscfg.guiding:
            autoguide = True

        if ob.inscfg.filter is None:
            # TODO: should we raise an error here?
            filtername = 'NOP'
        else:
            filtername = self.get_filtername(ob.inscfg.filter)


        d.update(dict(object=ob.target.name,
                      ra="%010.3f" % funky_ra, dec="%+010.2f" % funky_dec,
                      equinox=ob.target.equinox, pa=ob.inscfg.pa,
                      exptime=ob.inscfg.exp_time,
                      num_exp=ob.inscfg.num_exp,
                      offset_ra=ob.inscfg.offset_ra,
                      offset_dec=ob.inscfg.offset_dec,
                      dith1=ob.inscfg.dith1, dith2=ob.inscfg.dith2,
                      skip=ob.inscfg.skip, stop=ob.inscfg.stop,
                      filter=filtername,
                      autoguide=autoguide))

        # TODO: build guiding params from table as described below
        if autoguide:
            d1 = self.get_ag_exp(ob.inscfg.filter)
            guidestr = "GOODMAG=%(goodmag).1f AG_EXP=%(ag_exp).1f AG_AREA=SINGLE SELECT_MODE=SEMIAUTO" % d1
            d.update(dict(guidestr=guidestr))

        # prepare target parameters substring common to all SETUPFIELD
        # and GETOBJECT commands
        if ob.target not in self._tgts:
            tgtstr = 'OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f OFFSET_RA=%(offset_ra)d OFFSET_DEC=%(offset_dec)d Filter="%(filter)s"' % d
        else:
            # we have a named target defined for this
            d['tgtname'] = self._tgts[ob.target]
            tgtstr = '$%(tgtname)s INSROT_PA=%(pa).1f OFFSET_RA=%(offset_ra)d OFFSET_DEC=%(offset_dec)d Filter="%(filter)s"' % d

        d.update(dict(tgtstr=tgtstr))

    def write_ope_header(self, out_f, targets):

        out = self._mk_out(out_f)
        self._tgts = {}

        # prepare list of targets
        lines = ["# --- TARGETS ---"]
        count = 1
        for target in targets:
            name = self.mangle_name(target.name)
            d = dict(tgtname = "T%d_%s" % (count, name),
                     objname = target.name,
                     ra = self.ra_to_funky(target.ra),
                     dec = self.dec_to_funky(target.dec),
                     equinox = target.equinox)
            count += 1
            self._tgts[target] = d['tgtname']

            line = '''%(tgtname)s=OBJECT="%(objname)s" RA=%(ra)010.3f DEC=%(dec)+010.2f EQUINOX=%(equinox)6.1f''' % d
            lines.append(line)
        tgts_buf = '\n'.join(lines)

        preamble = """
:header
# this file was automatically generated at %(curtime)s
#
OBSERVATION_FILE_TYPE=OPE
#OBSERVATION_START_DATE=
#OBSERVATION_START_TIME=
#OBSERVATION_END_DATE=
#OBSERVATION_END_TIME=

:parameter
DEF_CMNTOOL=OBE_ID=COMMON OBE_MODE=TOOL
DEF_TOOLS=OBE_ID=HSC OBE_MODE=TOOLS
DEF_IMAGE=OBE_ID=HSC OBE_MODE=IMAG
DEF_IMAGE_VGW=OBE_ID=HSC OBE_MODE=IMAG_VGW
DEF_IMAGE5=OBE_ID=HSC OBE_MODE=IMAG_5
DEF_IMAGE5_VGW=OBE_ID=HSC OBE_MODE=IMAG_5_VGW
DEF_IMAGEN=OBE_ID=HSC OBE_MODE=IMAG_N
DEF_IMAGEN_VGW=OBE_ID=HSC OBE_MODE=IMAG_N_VGW

#GUIDE=EXPTIME_FACTOR=2 BRIGHTNESS=2000
#ZOPT=Z=7.00
Z=7.00

%(targets)s

:command

# *** PLEASE USE DOUBLE QUOTES("") FOR THE OBSERVER PARAMETER ***
#
QUEUE_MODE $DEF_CMNTOOL OBSERVER=

# These are here to copy in case you need to manually do a filterchange
# or focusing
#
#FilterChange1 $DEF_TOOLS FILTER="HSC-g"
#FilterChange2 $DEF_TOOLS FILTER="HSC-g" MIRROR=OPEN

#FOCUSOBE $DEF_IMAGE $TARGETNAME INSROT_PA=0.0 DELTA_Z=0.05 DELTA_DEC=5 FILTER="HSC-g" EXPTIME=10 Z=3.75

"""

        d = dict(curtime=time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime()),
                 targets=tgts_buf,
                 )
        out(preamble % d)

    def write_ope_trailer(self, out_f):
        out = self._mk_out(out_f)
        out("\n#######################################")
        out("\nCLASSICAL_MODE $DEF_CMNTOOL\n")

    def out_setup_ob(self, ob, out_f):
        out = self._mk_out(out_f)

        out("\n#######################################")
        d = dict(obid=str(ob), obname=ob.orig_ob.name,
                 propid=ob.program.propid,
                 proposal=ob.program.proposal,
                 observer='!FITS.HSC.OBSERVER',
                 pi=ob.program.pi,
                 tgtname=ob.target.name)
        # write out any comments
        out("\n## ob: %s" % (ob.comment))
        # TODO: need the comment from the root OB
        if len(ob.target.comment) > 0:
            out("\n## tgt: %s" % (ob.target.comment))
        if len(ob.inscfg.comment) > 0:
            out("\n## ins: %s" % (ob.inscfg.comment))
        if len(ob.envcfg.comment) > 0:
            out("\n## env: %s" % (ob.envcfg.comment))

        cmd_str = '''Start_OB $DEF_CMNTOOL OB_ID="%(obname)s" PROPOSAL="%(proposal)s" PROP_ID="%(propid)s" OBSERVER="%(observer)s" PROP_PI="%(pi)s"''' % d
        out(cmd_str)

    def out_focusobe(self, ob, out_f):
        out = self._mk_out(out_f)
        out("\n# focusing after filter change")

        d = {}
        self._setup_target(d, ob)

        cmd_str = '''FOCUSOBE $DEF_IMAGE %(tgtstr)s DELTA_Z=0.05 DELTA_DEC=5 EXPTIME=10 Z=3.75''' % d
        out(cmd_str)

    def out_filterchange(self, ob, out_f):
        out = self._mk_out(out_f)
        out("\n# %s" % (ob.comment))

        d = dict(filter=self.get_filtername(ob.inscfg.filter))
        # HSC uses two commands to change the filter
        cmd_str = '''FilterChange1 $DEF_TOOLS FILTER="%(filter)s"''' % d
        out(cmd_str)
        cmd_str = '''FilterChange2 $DEF_TOOLS FILTER="%(filter)s" MIRROR=OPEN''' % d
        out(cmd_str)

    def ob_to_ope(self, ob, out_f):

        out = self._mk_out(out_f)

        # special cases: filter change, long slew, calibrations, etc.
        if ob.derived:
            if ob.comment.startswith('Setup OB'):
                self.out_setup_ob(ob, out_f)
                return

            elif ob.comment.startswith('Filter change'):
                self.out_filterchange(ob, out_f)
                self.out_focusobe(ob, out_f)
                return

            elif ob.comment.startswith('Long slew'):
                out("\n# %s" % (ob.comment))
                d = {}
                self._setup_target(d, ob)
                cmd_str = '''SetupField $DEF_IMAGE %(tgtstr)s''' % d
                out(cmd_str)
                return

            elif ob.comment.startswith('Delay for'):
                out("\n# %s" % (ob.comment))
                d = dict(sleep_time=int(ob.total_time))
                cmd_str = '''EXEC OBS TIMER SLEEP_TIME=%(sleep_time)d''' % d
                out(cmd_str)
                return

            elif ob.comment.startswith('SDSS calibration'):
                out("\n# %s" % (ob.comment))
                d = {}
                self._setup_target(d, ob)
                # TODO: get this from the OB
                d['exptime'] = 30.0
                cmd_str = '''SetupField $DEF_IMAGE %(tgtstr)s''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGE %(tgtstr)s EXPTIME=%(exptime)d''' % d
                out(cmd_str)
                return

        tgtname = ob.target.name.lower()

        if tgtname == 'domeflat':
            out("\n# %s" % (ob.comment))
            cmd_str = 'SetupDomeFlat $DEF_CMNTOOL SETUP=SETUP  LAMP=4X10W VOLT=4.00 AMP=5.10'
            out(cmd_str)

            ## # Do we need this or will qplan make a filterchange OB for us?
            ## out("\n# Only execute this if you need to change the filter")
            ## self.out_filterchange(ob, out_f)

            out("\n# Take dome flats")
            d = dict(num_exp=ob.inscfg.num_exp, exptime=ob.inscfg.exp_time,
                     filter=self.get_filtername(ob.inscfg.filter))
            cmd_str = 'GetDomeFlat $DEF_IMAGE EXPTIME=%(exptime)d Filter="%(filter)s" NUMBER=%(num_exp)d' % d
            out(cmd_str)

            cmd_str = '''\nStop_OB $DEF_CMNTOOL\n'''
            out(cmd_str)
            return

        elif tgtname == 'bias':
            out("\n# %s" % (ob.comment))
            d = dict(num_exp=ob.inscfg.num_exp)
            cmd_str = 'GetBias $DEF_IMAGE NUMBER=%(num_exp)d' % d
            out(cmd_str)

            cmd_str = '''\nStop_OB $DEF_CMNTOOL\n'''
            out(cmd_str)
            return

        elif tgtname == 'dark':
            out("\n# %s" % (ob.comment))
            d = dict(num_exp=ob.inscfg.num_exp, exptime=ob.inscfg.exp_time)
            cmd_str = 'GetDark $DEF_IMAGE EXPTIME=%(exptime)d NUMBER=%(num_exp)d' % d
            out(cmd_str)

            cmd_str = '''\nStop_OB $DEF_CMNTOOL\n'''
            out(cmd_str)
            return

        elif tgtname == 'skyflat':
            d = {}
            self._setup_target(d, ob)
            cmd_str = '''SetupSkyFlat $DEF_IMAGE %(tgtstr)s %(guidestr)s''' % d
            out(cmd_str)

            cmd_str = '''GetSkyFlat $DEF_IMAGE %(tgtstr)s %(guidestr)s EXPTIME=%(exptime)d''' % d
            out(cmd_str)

            cmd_str = '''\nStop_OB $DEF_CMNTOOL\n'''
            out(cmd_str)
            return

        # <-- normal OBs
        out = self._mk_out(out_f)
        out("\n# %s" % (ob.comment))

        d = {}
        self._setup_target(d, ob)

        cmd_str = '''#FOCUSOBE $DEF_IMAGE %(tgtstr)s DELTA_Z=0.05 DELTA_DEC=5 EXPTIME=10 Z=3.75''' % d
        out(cmd_str)
        out("\n")

        if ob.inscfg.dither == '1':
            if ob.inscfg.guiding:
                cmd_str = '''SetupField $DEF_IMAGE_VGW %(tgtstr)s %(guidestr)s''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGE_VGW %(tgtstr)s %(guidestr)s EXPTIME=%(exptime)d''' % d
                out(cmd_str)
            else:
                cmd_str = '''SetupField $DEF_IMAGE %(tgtstr)s %(guidestr)s''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGE %(tgtstr)s %(guidestr)s EXPTIME=%(exptime)d''' % d
                out(cmd_str)

        elif ob.inscfg.dither == '5':
            if ob.inscfg.guiding:
                cmd_str = '''SetupField $DEF_IMAGE5_VGW %(tgtstr)s %(guidestr)s DITH_RA=%(dith1).1f DITH_DEC=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGE5_VGW %(tgtstr)s %(guidestr)s EXPTIME=%(exptime)d DITH_RA=%(dith1).1f DITH_DEC=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)
            else:
                cmd_str = '''SetupField $DEF_IMAGE5 %(tgtstr)s %(guidestr)s DITH_RA=%(dith1).1f DITH_DEC=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGE5 %(tgtstr)s %(guidestr)s EXPTIME=%(exptime)d DITH_RA=%(dith1).1f DITH_DEC=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)

        elif ob.inscfg.dither == 'N':
            if ob.inscfg.guiding:
                cmd_str = '''SetupField $DEF_IMAGEN_VGW %(tgtstr)s %(guidestr)s NDITH=%(num_exp)d RDITH=%(dith1).1f TDITH=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGEN_VGW %(tgtstr)s %(guidestr)s EXPTIME=%(exptime)d NDITH=%(num_exp)d RDITH=%(dith1).1f TDITH=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)
            else:
                cmd_str = '''SetupField $DEF_IMAGEN %(tgtstr)s %(guidestr)s NDITH=%(num_exp)d RDITH=%(dith1).1f TDITH=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGEN %(tgtstr)s %(guidestr)s EXPTIME=%(exptime)d NDITH=%(num_exp)d RDITH=%(dith1).1f TDITH=%(dith2).1f SKIP=%(skip)d STOP=%(stop)d''' % d
                out(cmd_str)

        else:
            raise ValueError("Instrument dither must be one of {1, 5, N}")

        cmd_str = '''\nStop_OB $DEF_CMNTOOL\n'''
        out(cmd_str)


    def mangle_name(self, name):
        for char in str(name):
            if not char in ope_friendly_chars:
                name = name.replace(char, '_')
        return name

    def get_filtername(self, name):
        name = name.upper()
        if name in filternames:
            return filternames[name]

        # narrowband filter
        if name.startswith('NB'):
            num = int(name[2:])
            name = "NB%04d" % num
        return "%s" % (name)

    def get_ag_exp(self, filter_name):

        filter_name = filter_name.lower()
        if filter_name in ag_exp_info:
            return ag_exp_info[filter_name]

        return ag_exp_info['g']

'''
########################################################################
# Commands for taking bias and dark.
#
# You can specify the number of bias/dark you want to take using
# the parameter "NUMBER".
#
# HSC-g, HSC-r, HSC-i, HSC-z, HSC-Y
########################################################################


#BIAS
GetBias $DEF_IMAGE NUMBER=5

#DARK
GetDark $DEF_IMAGE EXPTIME=300 NUMBER=3


########################################################################
# Filter Change Command
#
# Names of available filters:
#
# HSC-g, HSC-r, HSC-i, HSC-z, HSC-Y
########################################################################


FilterChange1 $DEF_TOOLS FILTER="HSC-r"
FilterChange2 $DEF_TOOLS FILTER="HSC-r"


########################################################################
# Following command is useful when you want to do focus test and
# take a shot at where telescope is pointed now.
########################################################################


FOCUSOBE $DEF_IMAGE OBJECT="FOCUS TEST" RA=!STATS.RA DEC=!STATS.DEC EQUINOX=2000.0 EXPTIME=10 Z=3.70 DELTA_Z=0.05 DELTA_DEC=5 Filter="HSC-r"

SetupField $DEF_IMAGE RA=!STATS.RA DEC=!STATS.DEC OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r"
GetObject $DEF_IMAGE RA=!STATS.RA DEC=!STATS.DEC EXPTIME=10 OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r"


########################################################################
# NGC77145
#
# OpenTracking (without AG), only one shot
# OFFSET can be specified in arcsec.
# The OFFSET value should be 3600 or smaller.
#
#  Note: For INSROT_PA, please refer the HSC instrument web page.
#        http://www.naoj.org/Observing/Instruments/HSC/ccd.html
########################################################################


FOCUSOBE $DEF_IMAGE $NGC77145 EXPTIME=10 Z=3.70 DELTA_Z=0.05 DELTA_DEC=5 Filter="HSC-r" INSROT_PA=0

SetupField $DEF_IMAGE $NGC77145 OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r" INSROT_PA=0
GetObject $DEF_IMAGE $NGC77145 EXPTIME=240 OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r" INSROT_PA=0

SetupField $DEF_IMAGE $NGC77145 OFFSET_RA=25 OFFSET_DEC=110 Filter="HSC-r" INSROT_PA=0
GetObject $DEF_IMAGE $NGC77145 EXPTIME=240 OFFSET_RA=25 OFFSET_DEC=110 Filter="HSC-r" INSROT_PA=0


########################################################################
# L1551
#
# OpenTracking (without AG), 5 shot dither.
# Dither pattern is as follows (relative to the center (0,0)).
#              RA,  DEC
#   1st pos:    0,    0
#   2nd pos:  1dx, -2dy
#   3rd pos:  2dx,  1dy
#   4th pos: -1dx,  2dy
#   5th pos: -2dx, -1dy
# where dx=DITH_RA and dy=DITH_DEC in arcsec.
########################################################################


FOCUSOBE $DEF_IMAGE $L1551 EXPTIME=10 Z=4.50 DELTA_Z=0.05 DELTA_DEC=5 Filter="HSC-r" INSROT_PA=90

SetupField $DEF_IMAGE5 $L1551 DITH_RA=120 DITH_DEC=120 OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r" INSROT_PA=90
GetObject $DEF_IMAGE5 $L1551 DITH_RA=120 DITH_DEC=120 EXPTIME=240 OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r" INSROT_PA=90


########################################################################
# OpenTracking (without AG), N shot dither.
# Dither pattern is as follows (relative to the center (0,0)).
#                Delta RA,         Delta DEC
#   1st pos:  R*cos(0*360/N+T), R*sin(0*360/N+T)
#   2nd pos:  R*cos(1*360/N+T), R*sin(1*360/N+T)
#   3rd pos:  R*cos(2*360/N+T), R*sin(2*360/N+T)
#      :             :                 :
#   Nth pos:  R*cos((N-1)*360/N+T), R*sin((N-1)*360/N+T)
# where N=NDITH, number of dither, R=RDITH in arcsec and T=TDITH in degree.
########################################################################


SetupField $DEF_IMAGEN $L1551 OFFSET_RA=0 OFFSET_DEC=0 NDITH=3 RDITH=120 TDITH=15 Filter="HSC-r" INSROT_PA=90
GetObject $DEF_IMAGEN $L1551 OFFSET_RA=0 OFFSET_DEC=0 EXPTIME=240 NDITH=3 RDITH=120 TDITH=15 Filter="HSC-r" INSROT_PA=90


########################################################################
# NGC6822
#
# AutoGuiding, only one shot. Guide star is selected interactively
# by VGW. Appropriate combinations of GOODMAG, and AG_EXP
# (GOODMAG, AG_EXP) are
#   (13.5, 0.2) FOR HSC-g,  (14.5, 0.2) FOR HSC-r
#   (14.0, 0.2) FOR HSC-i,  (13.0, 0.3) FOR HSC-z
#   (14,   0.3) FOR HSC-Y   ( ) FOR NB, but may vary by wavelength
# Note that these values are tentative ones, and also these values are
# changeable due to the weather conditions.
########################################################################


FOCUSOBE $DEF_IMAGE $NGC6822 EXPTIME=10 Z=3.70 DELTA_Z=0.05 DELTA_DEC=5 Filter="HSC-r" INSROT_PA=90

SetupField $DEF_IMAGE_VGW $NGC6822 OFFSET_RA=0 OFFSET_DEC=0 GOODMAG=14.5 AG_EXP=2 AG_AREA=SINGLE SELECT_MODE=SEMIAUTO Filter="HSC-r" INSROT_PA=90
GetObject  $DEF_IMAGE_VGW $NGC6822 EXPTIME=360 OFFSET_RA=0 OFFSET_DEC=0 GOODMAG=14.5 AG_EXP=2 AG_AREA=SINGLE SELECT_MODE=SEMIAUTO Filter="HSC-r" INSROT_PA=90


########################################################################
# NGC4038_39
#
# AutoGuiding, 5 shot dither. Guide star is seleceted interactively
# by VGW. Dither pattern is as above.
# Appropriate combinations of GOODMAG, and AG_EXP are as above.
# Note: this sequence (IMAGE5_VGW) is stopped when you cannot find
#       AG star. This is sometimes the case.
########################################################################


FOCUSOBE $DEF_IMAGE $NGC4038_39 EXPTIME=10 Z=3.70 DELTA_Z=0.05 DELTA_DEC=5 Filter="HSC-r" INSROT_PA=90

SetupField $DEF_IMAGE5_VGW $NGC4038_39 OFFSET_RA=0 OFFSET_DEC=0 DITH_RA=120 DITH_DEC=120 GOODMAG=14.5 AG_EXP=2 AG_AREA=SINGLE SELECT_MODE=SEMIAUTO Filter="HSC-r" INSROT_PA=90
GetObject  $DEF_IMAGE5_VGW $NGC4038_39 EXPTIME=360 OFFSET_RA=0 OFFSET_DEC=0 DITH_RA=120 DITH_DEC=120 GOODMAG=14.5 AG_EXP=2 AG_AREA=SINGLE SELECT_MODE=SEMIAUTO Filter="HSC-r" INSROT_PA=90


########################################################################
# AutoGuiding, N shot dither. Guide star is seleceted interactively
# by VGW. Dither pattern is as above.
# Appropriate combinations of GOODMAG, and AG_EXP are as above.
########################################################################


FOCUSOBE $DEF_IMAGE $NGC4038_39 EXPTIME=10 Z=4.50 DELTA_Z=0.05 DELTA_DEC=5 Filter="HSC-r" INSROT_PA=90

SetupField $DEF_IMAGEN_VGW $NGC4038_39 OFFSET_RA=0 OFFSET_DEC=0 NDITH=3 RDITH=120 TDITH=15 GOODMAG=14.5 AG_EXP=2 AG_AREA=SINGLE SELECT_MODE=SEMIAUTO Filter="HSC-r" INSROT_PA=90
GetObject  $DEF_IMAGEN_VGW $NGC4038_39 EXPTIME=360 OFFSET_RA=0 OFFSET_DEC=0 NDITH=3 RDITH=120 TDITH=15 GOODMAG=14.5 AG_EXP=2 AG_AREA=SINGLE SELECT_MODE=SEMIAUTO Filter="HSC-r" INSROT_PA=90


########################################################################
# NEO 1
#
# Non-Sidereal Tracking (without AG), only one shot
# OFFSET can be specified in arcsec.
# The OFFSET value should be 3600 or smaller.
########################################################################


SetupField $DEF_IMAGE $NEO1 OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r" INSROT_PA=90
GetObject $DEF_IMAGE $NEO1 EXPTIME=360 OFFSET_RA=0 OFFSET_DEC=0 Filter="HSC-r" INSROT_PA=90


########################################################################
# Standard Stars
#
# If you want to take bright standard stars (such as Landolt standards),
# specify DELTA_Z parameter to change focus value to the defocused position.
# DELTA_Z=0.4 works in most case with 5-10 sec exposure.
########################################################################


SetupField $DEF_IMAGE $SA107 OFFSET_RA=40 OFFSET_DEC=90 Filter="HSC-r" INSROT_PA=90
GetStandard $DEF_IMAGE $SA107 EXPTIME=5 DELTA_Z=0.4 OFFSET_RA=40 OFFSET_DEC=90 Filter="HSC-r" INSROT_PA=90


########################################################################
# Twilight Sky Flat
#
# Please use SetupSkyFlat command here.
#
# Appropriate exposure time will be calculated by instrument operator.
# Please ask for his/her assistance.
########################################################################

SetupSkyFlat $DEF_IMAGE RA=!STATS.RA DEC=!STATS.DEC OFFSET_RA=10 OFFSET_DEC=10 Filter="HSC-r"
GetSkyFlat $DEF_IMAGE RA=!STATS.RA DEC=!STATS.DEC EXPTIME=30 Filter="HSC-r"


########################################################################
# Dome Flat
#
# Please issue SetupDomeFlat command with SETUP=SETUP when you want to
# turn on the light. If the light is on, use SETUP=CHANGE to change
# the voltage and ampair. Appropriate combinations of VOLT, AMP and
# EXPTIME  (VOLT, AMP, EXPTIME) are,
#   (6.00, 6.30, 15) FOR HSC-g,  (4.00, 5.10, 17) FOR HSC-r
#   (4.00, 5.10,  7) FOR HSC-i,  (4.00, 5.10, 10) FOR HSC-z
#   (4.00, 5.10, 10) FOR HSC-Y
########################################################################

SetupDomeFlat $DEF_CMNTOOL SETUP=SETUP  LAMP=4X10W VOLT=4.00 AMP=5.10

FilterChange1 $DEF_TOOLS FILTER="HSC-r"
FilterChange2 $DEF_TOOLS FILTER="HSC-r"

GetDomeFlat $DEF_IMAGE EXPTIME=17 Filter="HSC-r"
GetDomeFlat $DEF_IMAGE EXPTIME=17 Filter="HSC-r" NUMBER=4


SetupDomeFlat $DEF_CMNTOOL SETUP=CHANGE LAMP=4X10W VOLT=4.00 AMP=5.10

FilterChange1 $DEF_SPCAM FILTER="HSC-i"
FilterChange2 $DEF_SPCAM FILTER="HSC-i"

GetDomeFlat $DEF_IMAGE EXPTIME=12 Filter="HSC-i"
GetDomeFlat $DEF_IMAGE EXPTIME=12 Filter="HSC-i" NUMBER=4

ShutdownDomeFlat $DEF_CMNTOOL
'''
#END
