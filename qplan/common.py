import pytz
from datetime import timedelta, tzinfo

import entity
from qplan.util import calcpos


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
