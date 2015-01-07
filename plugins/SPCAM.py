#
# SPCAM.py -- OB converter for SPCAM instrument
#
#  Eric Jeschke (eric@naoj.org)
#
import time

from q2ope import BaseConverter


class Converter(BaseConverter):

    def _setup_target(self, d, ob):
        
        funky_ra = self.ra_to_funky(ob.target.ra)
        funky_dec = self.dec_to_funky(ob.target.dec)
        
        d.update(dict(object=ob.target.name,
                      ra="%010.3f" % funky_ra, dec="%+010.2f" % funky_dec,
                      # TODO: specify PA in OBs?
                      equinox=ob.target.equinox, pa=90.0,
                      exptime=ob.inscfg.exp_time,
                      num_exp=ob.inscfg.num_exp,
                      filter=ob.inscfg.filter))
        
    def write_ope_header(self, out_f):

        out = self._mk_out(out_f)

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
DEF_SPCAM=OBE_ID=SPCAM OBE_MODE=IMAG
DEF_CMNTOOL=OBE_ID=COMMON OBE_MODE=TOOL

DEF_IMAGE=OBE_ID=SPCAM OBE_MODE=IMAG
DEF_IMAGE5=OBE_ID=SPCAM OBE_MODE=IMAG_5

DEF_IMAGE5_AG=OBE_ID=SPCAM OBE_MODE=IMAG_5_AG
DEF_IMAGE5_VGW=OBE_ID=SPCAM OBE_MODE=IMAG_5_VGW
DEF_IMAGE_AG=OBE_ID=SPCAM OBE_MODE=IMAG_AG
DEF_IMAGE_VGW=OBE_ID=SPCAM OBE_MODE=IMAG_VGW

DEF_IMAGEN=OBE_ID=SPCAM OBE_MODE=IMAG_N
DEF_IMAGEN_VGW=OBE_ID=SPCAM OBE_MODE=IMAG_N_VGW

GUIDE=EXPTIME_FACTOR=2 BRIGHTNESS=2000
ZOPT=Z=7.00       

:command
        """

        d = dict(curtime=time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime()),
                 )
        out(preamble % d)

    def out_focusobe(self, ob, out_f):
        out = self._mk_out(out_f)
        out("\n# %s" % (ob.comment))

        d = {}
        self._setup_target(d, ob)
        
        cmd_str = '''FOCUSOBE $DEF_IMAGE OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f EXPTIME=%(exptime)d Z=$Z DELTA_Z=0.05 DELTA_DEC=5 FILTER="%(filter)s"''' % d
        out(cmd_str)

    def out_filterchange(self, ob, out_f):
        out = self._mk_out(out_f)
        out("\n# %s" % (ob.comment))

        d = dict(filter=ob.inscfg.filter)
        cmd_str = '''FilterChange $DEF_SPCAM FILTER="%(filter)s"''' % d
        out(cmd_str)

    def ob_to_ope(self, ob, out_f):

        out = self._mk_out(out_f)

        # special cases: filter change, long slew, calibrations, etc.
        if ob.comment != '':
            if ob.comment.startswith('Filter change'):
                self.out_filterchange(ob, out_f)
                self.out_focusobe(ob, out_f)
                return
                
            elif ob.comment.startswith('Long slew'):
                d = {}
                self._setup_target(d, ob)
                cmd_str = '''SetupField $DEF_IMAGE OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f OFFSET_RA=0 OFFSET_DEC=0 Filter="%(filter)s"''' % d
                out(cmd_str)
                return

            elif ob.comment.startswith('Delay for'):
                d = dict(sleep_time=int(ob.totaltime))
                cmd_str = '''EXEC OBS TIMER SLEEP_TIME=%(sleep_time)d''' % d
                out(cmd_str)
                return

        # <-- normal OBs
        out = self._mk_out(out_f)

        out("\n# %s (%s %s) %s: %s" % (ob, ob.program.proposal,
                                       ob.program.pi, ob.name,
                                       ob.target.name))

        d = {}
        self._setup_target(d, ob)
        
        if ob.inscfg.mode == '1':
            if ob.inscfg.guiding:
                pass
            else:
                cmd_str = '''SetupField $DEF_IMAGE OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f OFFSET_RA=0 OFFSET_DEC=0 Filter="%(filter)s"''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGE OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f EXPTIME=%(exptime)d OFFSET_RA=0 OFFSET_DEC=0 Filter="%(filter)s"''' % d
                out(cmd_str)

        elif ob.inscfg.mode == '5':
            if ob.inscfg.guiding:
                pass
            else:
                cmd_str = '''SetupField $DEF_IMAGE5 OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f DITH_RA=60 DITH_DEC=60 OFFSET_RA=0 OFFSET_DEC=0 Filter="%(filter)s"''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGE5 OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f EXPTIME=%(exptime)d DITH_RA=60 DITH_DEC=60 OFFSET_RA=0 OFFSET_DEC=0 Filter="%(filter)s"''' % d
                out(cmd_str)

        elif ob.inscfg.mode == 'N':
            if ob.inscfg.guiding:
                pass
            else:
                cmd_str = '''SetupField $DEF_IMAGEN OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f NDITH=3 RDITH=60.0 TDITH=15 OFFSET_RA=0 OFFSET_DEC=0 Filter="%(filter)s"''' % d
                out(cmd_str)

                cmd_str = '''GetObject $DEF_IMAGEN OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f EXPTIME=%(exptime)d NDITH=%(num_exp)d RDITH=60.0 TDITH=15 OFFSET_RA=0 OFFSET_DEC=0 Filter="%(filter)s"''' % d
                out(cmd_str)

        else:
            raise ValueError("Instrument mode must be one of {1, 5, N}")



'''
SetupField $DEF_IMAGE $SA110 OFFSET_RA=0 OFFSET_DEC=30 Filter="W-J-B"
GetStandard $DEF_IMAGE $SA110 EXPTIME=5 DELTA_Z=0.4 OFFSET_RA=0 OFFSET_DEC=30 Filter="W-J-B"

SetupField $DEF_IMAGE_VGW $SA112 AG_SELECT=SEMIAUTO OFFSET_RA=0 OFFSET_DEC=0 Filter="W-S-Z+" 
GetObject  $DEF_IMAGE_VGW $SA112 AG_SELECT=SEMIAUTO OFFSET_RA=0 OFFSET_DEC=0 EXPTIME=20 Filter="W-S-Z+" 

Setupfield $DEF_IMAGE5 $SA113 DITH_RA=60 DITH_DEC=60 OFFSET_RA=0 OFFSET_DEC=0 Filter="W-S-Z+"
GetObject $DEF_IMAGE5 $SA113  DITH_RA=60 DITH_DEC=60 EXPTIME=20 OFFSET_RA=0 OFFSET_DEC=0 Filter="W-S-Z+"

Setupfield $DEF_IMAGE5_VGW $SA113 DITH_RA=60 DITH_DEC=60 OFFSET_RA=0 OFFSET_DEC=0 Filter="W-S-Z+"
GetObject $DEF_IMAGE5_VGW $SA113  DITH_RA=60 DITH_DEC=60 EXPTIME=20 OFFSET_RA=0 OFFSET_DEC=0 Filter="W-S-Z+"

SetupField $DEF_IMAGEN $SA113 OFFSET_RA=0 OFFSET_DEC=0 NDITH=3 RDITH=60.0 TDITH=
15 Filter="W-S-Z+" 
GetObject  $DEF_IMAGEN $SA113 OFFSET_RA=0 OFFSET_DEC=0 EXPTIME=20 NDITH=3 RDITH=
60.0 TDITH=15 Filter="W-S-Z+" 

SetupField $DEF_IMAGEN_VGW $GUIDE $NGC6705 OFFSET_RA=0 OFFSET_DEC=-320 NDITH=6 RDITH=25 TDITH=15 Filter="W-J-V" 
GetObject  $DEF_IMAGEN_VGW $GUIDE $NGC6705 OFFSET_RA=0 OFFSET_DEC=-320 EXPTIME=300 NDITH=6 RDITH=25.0 TDITH=15 Filter="W-J-V" 

# Skyflat
SetupField $DEF_IMAGE RA=!STATS.RA DEC=!STATS.DEC OFFSET_RA=10 OFFSET_DEC=10 Filter="W-J-B"
GetSkyFlat $DEF_IMAGE RA=!STATS.RA DEC=!STATS.DEC EXPTIME=30 Filter="W-J-B"

# Domeflat       
SetupDomeFlat $DEF_CMNTOOL SETUP=SETUP  LAMP=4X10W VOLT=6.00 AMP=6.33
GetDomeFlat $DEF_IMAGE EXPTIME=40 Filter="W-J-B"
'''
#END
