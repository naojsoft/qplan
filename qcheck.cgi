#!/usr/bin/env python

import cgi, os, sys, site
import cgitb; cgitb.enable()
import StringIO
import pandas as pd
import magic
import ldap
import datetime
import Cookie
import time
import hashlib
import pickle

sys.path.append('/gen2/share/Git/queuesim')
site.addsitedir('/gen2/share/arch/64/lib/python')
site.addsitedir('/gen2/share/arch/64/lib/python2.7/site-packages')

import filetypes, entity
from ginga.misc import log

STARS_LDAP_SERVER = 'squery.subaru.nao.ac.jp'
STARS_LDAP_PORT = 389
QUEUE_FILE_TOP_DIR = '/var/www/queue_files'
COOKIE_MAX_AGE = 3 * 60 * 60 # 3 hours

log_file = os.path.join(QUEUE_FILE_TOP_DIR, 'qcheck.log')
logger = log.get_logger(name='qcheck', level=20, log_file=log_file)

magic_types = {
    'xls':  'Composite Document File V2 Document',
    'xlsx': 'Zip archive data'
    }

def html_header(l, formatters=None):
    s = '<table border="1" class="dataframe"><thead><tr style="text-align: right;">'
    for item in l:
        s += '\n<th>'
        if formatters:
            try:
                s += formatters[item](item)
            except KeyError, e:
                s += item
        else:
            s += item
        s += '</th>'
    s += '\n</tr></thead></table>'
    return s

def upload_file(progFile, sessionValid, ldap_result, ldap_success, filename, file_buff):
    if progFile.error_count == 0 and (sessionValid or ldap_success):
        input_filename = os.path.basename(filename)
        propname, ext = input_filename.split('.')

        prop_id = progFile.cfg['proposal'].proposal_info['prop_id']
        prop_dir = os.path.join(QUEUE_FILE_TOP_DIR, prop_id)

        if not os.path.exists(prop_dir):
            os.mkdir(prop_dir)

        now = datetime.datetime.now()
        out_filename = '_'.join([propname, now.strftime('%Y%m%d_%H%M%S')])
        out_filename = '.'.join([out_filename, ext])
        out_pathname = os.path.join(prop_dir, out_filename)
        with open(out_pathname, 'w') as f:
            f.write(file_buff)
        print  """\
        <h3>Successfully uploaded file %s</h3>
        """ % (filename)
    else:
        if progFile.error_count > 0:
            print """\
            <h3>Error: Unable to upload file because error count is greater than 0</h3>
            """
        elif not sessionValid:
            if ldap_success is not None and not ldap_success:
                print """\
                <h3>Error: Unable to upload file because %s</h3>
                """ % ldap_result
            else:
                print """\
                <h3>Error: Unable to upload file because session has expired</h3>
                """

def report_msgs(d, severity):
    for name, l in d.iteritems():
        for row in l:
            row_num, col_name_list, msg = row
            msg = msg.replace('<', '&lt').replace('>', '&gt')
            if row_num is None:
                print """\
                <p>%s</p>
                """ % (msg)
            else:
                fmt = {}
                for col_name in col_name_list:
                    fmt[col_name] = lambda x: '<span class="%s">%s</span>' % (severity, ' ' if pd.isnull(x) else x)
                if row_num == 0:
                    col_names = list(progFile.df[name])
                    print  """\
                    <p>%s<br>%s</p>
                    """ % (msg, html_header(col_names, formatters=fmt))
                else:
                    print """\
                    <p>%s<br>%s</p>
                    """ % (msg, progFile.df[name][row_num-1:row_num].to_html(index=False, na_rep='', formatters=fmt, escape=False))

def stars_ldap_connect(username, password):
    l=ldap.open(STARS_LDAP_SERVER, STARS_LDAP_PORT)
    loginline="uid="+username+",ou=People,dc=stars,dc=nao,dc=ac,dc=jp"
    try:
        l.simple_bind_s(loginline, password)
    except:
        # ldap bind fail
        result="STARS Login/Password Failed or Account is Locked"
        success = False
    else:
        result="STARS Login succeeded"
        success = True

    return result, success

def createServerCookie():
    c = Cookie.SimpleCookie()
    h = hashlib.sha1()
    h.update( repr( time.time() ) )
    sid = h.hexdigest()
    c['qcheck-session-id'] = sid
    c['qcheck-session-id']['max-age'] = COOKIE_MAX_AGE
    now = datetime.datetime.now()
    c['qcheck-session-start-timestamp'] = now.isoformat()
    end = now + datetime.timedelta(seconds=COOKIE_MAX_AGE)
    c['qcheck-session-end-timestamp'] = end.isoformat()
    logger.info('server cookie %s' % c)
    return c

def getSessionCookieFilepath(sid):
    session_cookie_filename = 'session_' + sid + '.pickle'
    session_cookie_filepath = os.path.join(QUEUE_FILE_TOP_DIR, session_cookie_filename)
    return session_cookie_filepath

def saveCookie(c):
    session_cookie_filepath = getSessionCookieFilepath(c['qcheck-session-id'].value)
    try:
        with open(session_cookie_filepath, 'wb') as f:
            pickle.dump(c, f)
    except IOError:
        logger.error('Unable to open cookie pickle file %s' % session_cookie_filepath)

def getClientCookie():
    if 'HTTP_COOKIE' in os.environ:
        c = Cookie.SimpleCookie()
        c.load(os.environ['HTTP_COOKIE'])
        logger.info('HTTP_COOKIE is %s' % c)
        try:
            sid = c['qcheck-session-id'].value
        except KeyError:
            sid = None
        logger.info('qcheck-session-id in cookie is %s' % sid)
        return c
    else:
        return None

def getTimestampFromCookie(c, key):
    return datetime.datetime.strptime(c[key].value, '%Y-%m-%dT%H:%M:%S.%f')

def validateSession(cookieFromClient):
    try:
        sid = cookieFromClient['qcheck-session-id'].value
    except TypeError:
        logger.error('TypeError getting qcheck-session-id from client cookie')
        sid = None
        return False
    except KeyError:
        logger.error('KeyError getting qcheck-session-id from client cookie')
        sid = None
        return False

    session_cookie_filepath = getSessionCookieFilepath(sid)
    try:
        with open(session_cookie_filepath, 'rb') as f:
            serverCookie = pickle.load(f)
    except IOError:
        logger.error('Unable to open cookie pickle file %s' % session_cookie_filepath)
        return False
    logger.info('cookieFromClient %s' % cookieFromClient)
    logger.info('serverCookie %s' % serverCookie)
    now = datetime.datetime.now()
    qcheck_session_end_timestamp = getTimestampFromCookie(serverCookie, 'qcheck-session-end-timestamp')
    if cookieFromClient['qcheck-session-id'].value == serverCookie['qcheck-session-id'].value and now < qcheck_session_end_timestamp:
        logger.info('Session validated')
        return True
    else:
        logger.info('Session not validated')
        return False

form = cgi.FieldStorage()

# Check to see if there is a cookie in the HTTP request and if we can
# validate the session.
cc = getClientCookie()
sessionValid = validateSession(cc)
if sessionValid:
    sc = cc
else:
    sc = None

# Check to see if the user clicked on the Upload button
try:
    upload = form['upload'].value
except KeyError:
    upload = None

# If upload was clicked and we weren't able to validate the session,
# see if we can validate the username/password in STARS LDAP.
ldap_success = None
ldap_result = None
if upload and not sessionValid:
    try:
        username = form['username'].value
        password = form['password'].value
    except KeyError:
        ldap_result = 'Username/password not supplied'
    else:
        ldap_result, ldap_success = stars_ldap_connect(username, password)
        logger.info('ldap_result %s' % ldap_result)

    if ldap_success:
        logger.info('creating server cookie')
        sc = createServerCookie()
        saveCookie(sc)
        sessionValid = True
    else:
        sc = None

# HTML header and CSS information
if sessionValid:
    print sc
print """\
Content-Type: text/html\n
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<meta name="Robots" content="NOINDEX,NOFOLLOW">
<meta name="Keywords" content="">
<meta name="Author" content="Russell Kackley">
<meta name="Generator" content="emacs and human">
<meta name="Copyright" content="&copy; 200X  Russell Kackley">
<title>Subaru Queue File Checker</title>
<style>
.ok      {background-color: white}
.warning {background-color: yellow}
.error   {background-color: red}
</style>
</head>
<body>
<h1>Subaru Queue File Checker</h1>
"""

# The form element
print """\
<form enctype="multipart/form-data" action="/cgi-bin/qcheck/qcheck.cgi" method="POST">
<input type="hidden" name="logLevel" value="30">
File name(s) (must be Excel file format):
<input type="file" name="filename" multiple>
<hr>
<br>
<input type="submit" name="check"  value="Check">
(Username/password not required for checking the file)
<hr>
"""
if sessionValid:
    print 'Session is valid until HST %s (Username/password not currently required)<br>' % getTimestampFromCookie(sc, 'qcheck-session-end-timestamp').strftime('%c')
else:
    print """\
    <p>
    For file upload, enter STARS username and password:
    <br>
    <label for="name">STARS Userame</label>
    <input type="text" name="username" id="username" value="">
    <br>
    <label for="password">STARS Password</label>
    <input type="password" name="password" id="password" value="">
    <br>
    """
print """\
<input type="submit" name="upload" value="Upload">
</form> 
"""

try:
    # Get file and log level information here.
    fileitem = form['filename']
    logLevel = form['logLevel']
except KeyError:
    # If no filename/logLevel, exit immediately
    sys.exit(1)

# If the user selected several files, fileitem will be a
# list. Otherwise, fileitem will be a scalar. Either way set up a list
# with the contents from fileitem.
try:
    fileList = [item for item in fileitem]
except TypeError:
    fileList = [fileitem]

if upload and ldap_success is not None:
    if ldap_success:
        print 'STARS LDAP result: %s' % ldap_result
    else:
        print '<h3>STARS LDAP result: %s</h3>' % ldap_result

if len(fileList[0].filename) > 0:

    ms = magic.open(magic.MAGIC_ERROR)
    ms.load()

    for item in fileList:
        print """\
        <p>Reading file %s</p>
        """ % (item.filename)

        progFile = None
        input_filename = os.path.basename(item.filename)
        propname, ext = input_filename.split('.')
        # We expect the file extension to be either .xls or .xlsx
        if ext in filetypes.QueueFile.excel_ext:
            file_ext_ok = True
        else:
            file_ext_ok = False

        # Check the "magic type" of the file to see if it matches what
        # we expect for a .xls or .xlsx file.
        file_buff = item.file.read()
        magic_filetype = ms.buffer(file_buff)
        if ms.error() is not None:
            print """\
            <p>Error getting magic filetype from file %s: %s</p>
            """ % (item.filename, ms.error())
            logger.error(ms.error())
        try:
            if magic_types[ext] in magic_filetype:
                magic_filetype_ok = True
            else:
                magic_filetype_ok = False
        except KeyError as e:
            magic_filetype_ok = False

        if file_ext_ok and magic_filetype_ok:
            propdict = {}
            key = propname.upper()
            propdict[key] = entity.Program(key, hours=0, category='')
            progFile = filetypes.ProgramFile('', logger, propname, propdict, file_ext=ext, file_obj=item.file)
        else:
            if not file_ext_ok:
                msg = "File extension '%s' is not a valid file type. Must be one of %s." % (ext, filetypes.QueueFile.excel_ext)
                logger.error(msg)
                print """\
                <p>%s</p>
                """ % (msg)
            if not magic_filetype_ok:
                msg = "Unexpected magic file type '%s' detected. This does not seem to be an Excel file." % (magic_filetype)
                logger.error(msg)
                print """\
                <p>%s</p>
                """ % (msg)

        if progFile:
            print """\
            <h3>File Check Results From File %s:</h3>
            """ % (item.filename)
            if progFile.warn_count == 0 and progFile.error_count == 0:
                print """\
                <p><span class="ok">Warning</span> count is %d</p>
                <p><span class="ok">Error</span> count is %d</p>
                """ % (progFile.warn_count, progFile.error_count)
                print """\
                File %s is <span class="ok">ok</span>.
                """ % (item.filename)
            else:
                print """\
                <p><span class="%s">Warning</span> count is %d</p>
                """ % ('warning' if progFile.warn_count >0 else 'ok', progFile.warn_count)
                report_msgs(progFile.warnings, 'warning')
                print """\
                <p><span class="%s">Error</span> count is %d</p>
                """ % ('error' if progFile.error_count >0 else 'ok', progFile.error_count)
                report_msgs(progFile.errors, 'error')

                if upload:
                    upload_file(progFile, sessionValid, ldap_result, ldap_success, item.filename, file_buff)

    ms.close()
else:
    print """\
    <p>Unable to read file - filename is empty</p>
    """

print """\
</body>
</html>
"""
