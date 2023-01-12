from . import entity
from .util import calcpos

# Extra overhead time charged to proposals on top of readout + on src time
# https://www.naoj.org/Observing/Instruments/HSC/hsc_queue_overhead.html
hsc_extra_overhead_factor = 1.137


# The common solar system bodies
moon = entity.StaticTarget(name="Moon")
moon.body = calcpos.Moon
sun = entity.StaticTarget(name="Sun")
sun.body = calcpos.Sun
mercury = entity.StaticTarget(name="Mercury")
mercury.body = calcpos.Mercury
venus = entity.StaticTarget(name="Venus")
venus.body = calcpos.Venus
mars = entity.StaticTarget(name="Mars")
mars.body = calcpos.Mars
jupiter = entity.StaticTarget(name="Jupiter")
jupiter.body = calcpos.Jupiter
saturn = entity.StaticTarget(name="Saturn")
saturn.body = calcpos.Saturn
uranus = entity.StaticTarget(name="Uranus")
uranus.body = calcpos.Uranus
neptune = entity.StaticTarget(name="Neptune")
neptune.body = calcpos.Neptune
pluto = entity.StaticTarget(name="Pluto")
pluto.body = calcpos.Pluto
