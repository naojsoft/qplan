import os
import time
from io import StringIO

major = 0
minor = 5

rlfile = 'version.py'
backup = 'version.py.bak'

def make_release():
    release = time.strftime("%Y%m%d%H%M%S", time.gmtime(time.time()))
    release = int(release)

    if os.path.exists(backup):
        os.remove(backup)

    if os.path.exists(rlfile):
        os.rename(rlfile, backup)

    buf = StringIO()

    buf.write("# this file was automatically generated\n")
    buf.write("major = %d\n" % major)
    buf.write("minor = %d\n" % minor)
    buf.write("release = %d\n" % release)
    buf.write("\n")
    buf.write("version = '%d.%d.%d' % (major, minor, release)\n")
    buf.write("\n")

    with open(rlfile, 'w') as out_f:
        out_f.write(buf.getvalue())

    return '%d.%d.%d' % (major, minor, release)

if __name__ == "__main__":
    print(make_release())
