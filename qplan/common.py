from .util import calcpos

# Extra overhead time charged to proposals on top of readout + on src time
# https://www.naoj.org/Observing/Instruments/HSC/hsc_queue_overhead.html
#
# Note: Starting in S24A, the HSC Queue Phase 2 spreadsheets have an
# "Acct Time" column that computes the "accounting time" using the
# "hsc_extra_overhead_factor" in the calculation. We'll retain this
# factor in the code until we are sure that we no longer need to read
# any pre-S24A spreadsheets.
hsc_extra_overhead_factor = 1.137


# The common solar system bodies
moon = calcpos.Moon
sun = calcpos.Sun
mercury = calcpos.Mercury
venus = calcpos.Venus
mars = calcpos.Mars
jupiter = calcpos.Jupiter
saturn = calcpos.Saturn
uranus = calcpos.Uranus
neptune = calcpos.Neptune
pluto = calcpos.Pluto
