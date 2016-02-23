import pytz
import entity
import ephem

# Subaru Telescope
subaru = entity.Observer('subaru',
                         longitude='-155:28:48.900',
                         latitude='+19:49:42.600',
                         elevation=4163,
                         pressure=615,
                         temperature=0,
                         timezone=pytz.timezone('US/Hawaii'))

# The common solar system bodies
moon = entity.StaticTarget(name="Moon")
moon.body = ephem.Moon()
sun = entity.StaticTarget(name="Sun")
sun.body = ephem.Sun()
mercury = entity.StaticTarget(name="Mercury")
mercury.body = ephem.Mercury()
venus = entity.StaticTarget(name="Venus")
venus.body = ephem.Venus()
mars = entity.StaticTarget(name="Mars")
mars.body = ephem.Mars()
jupiter = entity.StaticTarget(name="Jupiter")
jupiter.body = ephem.Jupiter()
saturn = entity.StaticTarget(name="Saturn")
saturn.body = ephem.Saturn()
uranus = entity.StaticTarget(name="Uranus")
uranus.body = ephem.Uranus()
neptune = entity.StaticTarget(name="Neptune")
neptune.body = ephem.Neptune()
pluto = entity.StaticTarget(name="Pluto")
pluto.body = ephem.Pluto()
        
