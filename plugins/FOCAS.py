#
# FOCAS.py -- OB converter for FOCAS instrument
#
#  Eric Jeschke (eric@naoj.org)
#
import time

from ginga import trcalc
from q2ope import BaseConverter


class Converter(BaseConverter):

    def _setup_target(self, d, ob):
        
        funky_ra = self.ra_to_funky(ob.target.ra)
        funky_dec = self.dec_to_funky(ob.target.dec)

        autoguide = 'NO'
        if ob.inscfg.guiding:
            autoguide = 'YES'
        
        d.update(dict(object=ob.target.name,
                      ra="%010.3f" % funky_ra, dec="%+010.2f" % funky_dec,
                      equinox=ob.target.equinox, pa=ob.inscfg.pa,
                      exptime=ob.inscfg.exp_time,
                      num_exp=ob.inscfg.num_exp,
                      dither_ra=ob.inscfg.dither_ra,
                      dither_dec=ob.inscfg.dither_dec,
                      dither_theta=ob.inscfg.dither_theta,
                      binning=ob.inscfg.binning,
                      offset_sec=ob.inscfg.offset_ra,
                      filter=ob.inscfg.filter.upper(),
                      autoguide=autoguide))

        # prepare target parameters substring common to all SETUPFIELD
        # and GETOBJECT commands
        tgtstr = 'OBJECT="%(object)s" RA=%(ra)s DEC=%(dec)s EQUINOX=%(equinox)6.1f INSROT_PA=%(pa).1f $FILTER_BB_%(filter)s' % d
        d.update(dict(tgtstr=tgtstr))

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
*LOAD "FOCAS_FOCASPARAM.prm"
*LOAD "FOCAS_MOS.prm"
*LOAD "FOCAS_STDSTAR.prm"

:command
        """

        d = dict(curtime=time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime()),
                 )
        out(preamble % d)

    def ob_to_ope(self, ob, out_f):

        out = self._mk_out(out_f)

        # special cases: filter change, long slew, calibrations, etc.
        if ob.comment != '':
            if ob.comment.startswith('Filter change'):
                #self.out_filterchange(ob, out_f)
                return
                
            elif ob.comment.startswith('Long slew'):
                out("\n# %s" % (ob.comment))
                d = {}
                self._setup_target(d, ob)
                cmd_str = 'SetupField $DEF_IMAG %(tgtstr)s $MASK_NONE Shift_Sec=%(offset_sec)d' % d
        
                if ob.inscfg.guiding:
                    cmd_str = cmd_str + (' AUTOGUIDE=%(autoguide)s' % d)
                out(cmd_str)
                return

            elif ob.comment.startswith('Delay for'):
                out("\n# %s" % (ob.comment))
                d = dict(sleep_time=int(ob.total_time))
                cmd_str = 'EXEC OBS TIMER SLEEP_TIME=%(sleep_time)d' % d
                out(cmd_str)
                return

        # <-- normal OBs
        out = self._mk_out(out_f)

        out("\n# %s (%s %s) %s: %s" % (ob, ob.program.proposal,
                                       ob.program.pi, ob.name,
                                       ob.target.name))

        d = {}
        self._setup_target(d, ob)

        cmd_str = 'SetupField $DEF_IMAG %(tgtstr)s $MASK_NONE Shift_Sec=%(offset_sec)d' % d
        
        if ob.inscfg.guiding:
            dith_cmd = "MoveGuide0"
            cmd_str = cmd_str + (' AUTOGUIDE=%(autoguide)s' % d)
        else:
            dith_cmd = "MoveTelescope"
            cmd_str = cmd_str + (' AUTOGUIDE=%(autoguide)s' % d)

        # output setupfield command to position telescope
        out(cmd_str)

        d_ra, d_dec = d['dither_ra'], d['dither_dec']
        d_theta = d['dither_theta']
        
        abs_off = ((0, 0), (d_ra, d_dec), (-d_dec, d_ra), (-d_ra, -d_dec),
                   (d_dec, -d_ra), (0, 0))
        # rotate box points according to dither theta
        abs_off = map(lambda p: trcalc.rotate_pt(p[0], p[1], d_theta), abs_off)

        # 5 dither sequence
        d['mask'] = 'NONE'

        for i in xrange(5):
            out("# Dither point %d" % (i+1))
            cmd_str = 'GetObject $DEF_IMAG $MASK_%(mask)s %(tgtstr)s $CCD_%(binning)s EXPTIME=%(exptime)d' % d
            out(cmd_str)

            # calculate deltas for positioning at next dither pos
            cur_off_ra, cur_off_dec = abs_off[i]
            #print("current off ra, dec=%.3f,%.3f" % (cur_off_ra, cur_off_dec))
            next_off_ra, next_off_dec = abs_off[i+1]
            #print("next off ra, dec=%.3f,%.3f" % (next_off_ra, next_off_dec))
            delta_ra = next_off_ra - cur_off_ra
            delta_dec = next_off_dec - cur_off_dec

            # issue command for offsetting to next dither pos
            cmd_str = '%s $DEF_TOOL Delta_RA=%.3f Delta_DEC=%.3f' % (
                dith_cmd, delta_ra, delta_dec)
            out(cmd_str)

            d['mask'] = 'NOP'
            #cur_off_ra, cur_off_dec = next_off_ra, next_off_dec

'''
# Broad Band (BB) #


FILTER_NONE=Grism=0 Filter01=0 Filter02=0 Filter03=0 Polarizer=Nop
FILTER_BB_U=Grism=0 Filter01=1 Filter02=0 Filter03=0 Polarizer=Nop
FILTER_BB_B=Grism=0 Filter01=2 Filter02=0 Filter03=0 Polarizer=Nop
FILTER_BB_V=Grism=0 Filter01=3 Filter02=0 Filter03=0 Polarizer=Nop
FILTER_BB_R=Grism=0 Filter01=4 Filter02=0 Filter03=0 Polarizer=Nop
FILTER_BB_I=Grism=0 Filter01=5 Filter02=0 Filter03=0 Polarizer=Nop


# Narrow Band (NB) #


#FILTER_NB_373=Grism=0 Filter01=0 Filter02=0 Filter03=5 Polarizer=Nop
#FILTER_NB_386=Grism=0 Filter01=0 Filter02=0 Filter03=7 Polarizer=Nop
#FILTER_NB_487=Grism=0 Filter01=7 Filter02=0 Filter03=0 Polarizer=Nop
#FILTER_NB_502=Grism=0 Filter01=0 Filter02=1 Filter03=0 Polarizer=Nop
#FILTER_NB_512=Grism=0 Filter01=0 Filter02=2 Filter03=0 Polarizer=Nop
#FILTER_NB_642=Grism=0 Filter01=0 Filter02=3 Filter03=0 Polarizer=Nop
#FILTER_NB_658=Grism=0 Filter01=0 Filter02=4 Filter03=0 Polarizer=Nop
#FILTER_NB_670=Grism=0 Filter01=0 Filter02=5 Filter03=0 Polarizer=Nop
FILTER_NB_373=Grism=0 Filter01=0 Filter02=5 Filter03=0 Polarizer=Nop
#FILTER_NB_386=Grism=0 Filter01=0 Filter02=5 Filter03=0 Polarizer=Nop
#FILTER_NB_487=Grism=0 Filter01=7 Filter02=0 Filter03=0 Polarizer=Nop
FILTER_NB_502=Grism=0 Filter01=0 Filter02=4 Filter03=0 Polarizer=Nop
FILTER_NB_512=Grism=0 Filter01=0 Filter02=2 Filter03=0 Polarizer=Nop
#FILTER_NB_642=Grism=0 Filter01=0 Filter02=0 Filter03=7 Polarizer=Nop
FILTER_NB_658=Grism=0 Filter01=0 Filter02=0 Filter03=5 Polarizer=Nop
#FILTER_NB_670=Grism=0 Filter01=0 Filter02=4 Filter03=0 Polarizer=Nop


# Narrow Band (NB) alias #


#FILTER_NB_O2_ON=Grism=0 Filter01=0 Filter02=0 Filter03=5 Polarizer=Nop
#FILTER_NB_O2_OFF=Grism=0 Filter01=0 Filter02=0 Filter03=6 Polarizer=Nop
#FILTER_NB_HB_ON=Grism=0 Filter01=0 Filter02=0 Filter03=7 Polarizer=Nop
#FILTER_NB_HB_OFF=Grism=0 Filter01=0 Filter02=1 Filter03=0 Polarizer=Nop
#FILTER_NB_O3_ON=Grism=0 Filter01=0 Filter02=2 Filter03=0 Polarizer=Nop
#FILTER_NB_HA_ON=Grism=0 Filter01=0 Filter02=3 Filter03=0 Polarizer=Nop
#FILTER_NB_HA_OFF=Grism=0 Filter01=0 Filter02=4 Filter03=0 Polarizer=Nop
#FILTER_NB_S2_ON=Grism=0 Filter01=0 Filter02=5 Filter03=0 Polarizer=Nop

# Polarizing filters (PF) #


FILTER_PF_OPT=Filter03=3
FILTER_PF_NIR=Filter03=4

# SDSS filterS
FILTER_BB_Z=Grism=0 Filter01=0 Filter02=0 Filter03=1 Polarizer=Nop
FILTER_SDSS_Z=Grism=0 Filter01=0 Filter02=0 Filter03=1 Polarizer=Nop
FILTER_SDSS_I=Grism=0 Filter01=7 Filter02=0 Filter03=0 Polarizer=Nop
FILTER_SDSS_R=GRISM=0 FILTER01=0 FILTER02=0 FILTER03=7 POLARIZER=NOP
FILTER_SDSS_G=GRISM=0 FILTER01=0 FILTER02=1 FILTER03=0 POLARIZER=NOP
FILTER_BB_G=GRISM=0 FILTER01=0 FILTER02=1 FILTER03=0 POLARIZER=NOP

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

How to convert SHIFT_SEC to Delta_RA and Delta_DEC depends
on the position angle.
From the skelton file,
 Delta_RA = SHIFT_SEC * sin (PA)
 Delta_Dec= SHIFT_SEC * cos (PA)
It is in arcsec.

> 2) For the standard 5 point dither, what would be a typical value
> for the MoveGuide0 offset in DELTA_RA and DELTA_DEC?
> In other words, what is the absolute value of the offset from
> the origin for each point?

Let's use a tilted square.
In absolute coordinates,
 (0,0)
 (8,2)
 (-2,8)
 (-8,-2)
 (2,-8)

MoveGuide0 is the offset from the current position.
So, for the above dithering pattern, we need
 GetObject ...
 MoveGuide0 $DEF_TOOL DELTA_RA=8 DELTA_DEC=2
 GetObject ...
 MoveGuide0 $DEF_TOOL DELTA_RA=-10 DELTA_DEC=6
 GetObject ...
 MoveGuide0 $DEF_TOOL DELTA_RA=-6 DELTA_DEC=-10
 GetObject ...
 MoveGuide0 $DEF_TOOL DELTA_RA=10 DELTA_DEC=-6
 GetObject ...
 MoveGuide0 $DEF_TOOL DELTA_RA=-2 DELTA_DEC=8 

'''
#END
