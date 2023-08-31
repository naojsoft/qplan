from dateutil import tz, parser
from datetime import timedelta


def get_semester_by_datetime(dt, tz_local):
    """Figure out a semester by looking at the time something was
    observed.

    Parameters
    ----------
    dt : datetime.datetime
        The date/time that something was observered (like an OB)

    tz_local : dateutil.tz.tz.tzfile
        The local time zone for observation

    Returns
    -------
    sem : str
        A string of the form "S{YY}[AB]"
    """
    if dt.tzinfo is None:
        # tag with timezone UTC if it is not already tagged
        dt = dt.replace(tzinfo=tz.UTC)
    # convert to local time
    dt = dt.astimezone(tz_local)
    # if observation is after midnight, but before 8am, dial date back
    # to previous day (should take care of observations after midnight
    # on the last day of the last month of the semester)
    if 0 <= dt.hour < 8:
        dt = dt - timedelta(0, hours=8, minutes=30)
    year, mon = dt.year, dt.month
    if mon == 1:
        # if month is January, dial back the year
        # (semester "A" starts Feb 1)
        year -= 1
    sem = 'A' if mon in (2, 3, 4, 5, 6, 7) else 'B'
    yr  = str(year)[-2:]
    return f"S{yr}{sem}"

def get_datetimes_by_semester(sem, tz_local):
    """Figure out the beginning and ending datetimes for a semester.

    Parameters
    ----------
    sem : str
        A string of the form "S{YY}[AB]"

    tz_local : dateutil.tz.tz.tzfile
        The local time zone for observation

    Returns
    -------
    (dt_start, dt_stop) : tuple of datetime.datetime
    """
    sem = sem.upper()
    year = 2000 + int(sem[1:3])
    if sem.endswith('A'):
        dt_start = parser.parse(f"{year:04d}-02-01 12:00:00")
        dt_stop = parser.parse(f"{year:04d}-08-01 11:59:59")
    else:
        dt_start = parser.parse(f"{year:04d}-08-01 12:00:00")
        year += 1
        dt_stop = parser.parse(f"{year:04d}-02-01 11:59:59")

    # tag with timezone
    dt_start = dt_start.replace(tzinfo=tz_local)
    dt_stop = dt_stop.replace(tzinfo=tz_local)

    return dt_start, dt_stop
