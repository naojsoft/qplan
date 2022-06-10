#!/gen2/share/miniconda3/envs/py37/bin/python

import cgi, os, sys, site
import cgitb; cgitb.enable()
import pandas as pd
import magic
import ldap3
import datetime
import http.cookies
import time
import hashlib
import pickle
import re
import os
import smtplib

from qplan import filetypes, entity, promsdb
from qplan.cfg import email_cfg
from ginga.misc import log

STARS_LDAP_SERVER = 'squery.subaru.nao.ac.jp'
STARS_LDAP_PORT = 389
QUEUE_FILE_TOP_DIR = '/var/www/queue_files'
COOKIE_MAX_AGE = 3 * 60 * 60 # 3 hours

# Set column width greater than the maximum to accommodate long
# filenames in "Uploaded Files" output listing.
pd.set_option('max_colwidth', 80)

log_file = os.path.join(QUEUE_FILE_TOP_DIR, 'qcheck.log')
logger = log.get_logger(name='qcheck', level=20, log_file=log_file)


# Set user_filetype depending on whether we were invoked from the
# qcheck.cgi script or the qcheck_xls.cgi script.

if 'xls' in  os.path.basename(__file__):
    user_filetype = 'Excel_file'
else:
    user_filetype = 'Google_sheet'

title_str = {'Excel_file': {'str1': 'File', 'str2': 'Uploader'},
             'Google_sheet': {'str1': 'Google Sheet', 'str2': 'Submitter'},
             }

alternate_url = {'Excel_file': 'This page is for checking/uploading Excel files. For checking/submitting Google Sheets, <a href="/cgi-bin/qcheck/qcheck.cgi">click here</a>',
                 'Google_sheet': '',
    }

# Form element action and input prompt depend on whether we are
# uploading from user's Excel file or downloading from Google Sheet.
form_element = {'Excel_file': {'action': '/cgi-bin/qcheck/qcheck_xls.cgi',
                               'input_prompt': 'File name for checking or uploading (must be Excel file format): <input type="file" name="filename">',
                               'instructions': 'Welcome to the Subaru Excel File Checker/Uploader/Listing site',
                               'button_label': 'Upload',
                               'file_type_str': 'Excel file',
                               'upload_or_submit': 'uploads',
                               'list_instructions': 'names of the files that have been uploaded',
                               'list_caption': 'uploaded files',
                               'list_button_label': 'List files',
                          },
                'Google_sheet':  {'action': '/cgi-bin/qcheck/qcheck.cgi',
                                  'input_prompt': 'Google Sheet name for checking or submitting <input type="text" size="20" name="gsheetname", value=""> (e.g., S22B-QN001)',
                                  'instructions': 'Welcome to the Subaru Google Sheet Checker/Submitter/Listing site',
                                  'button_label': 'Submit',
                                  'file_type_str': 'Google Sheet',
                                  'upload_or_submit': 'submissions',
                                  'list_instructions': 'Google Sheet submission timestamps',
                                  'list_caption': 'submission timestamps',
                                  'list_button_label': 'List submissions',
                                 },
                }

upload_err_msg = {'Excel_file': 'upload file',
                  'Google_sheet': 'submit Google Sheet',
                  }

magic_types = {
    'xls':  ['Composite Document File V2 Document',],
    'xlsx': ['Zip archive data', 'Microsoft Excel 2007+', 'Microsoft OOXML']
    }

def html_header(l, formatters=None):
    s = '<table border="1" class="dataframe"><thead><tr style="text-align: right;">'
    for item in l:
        s += '\n<th>'
        if formatters:
            try:
                s += formatters[item](item)
            except KeyError as e:
                s += item
        else:
            s += item
        s += '</th>'
    s += '\n</tr></thead></table>'
    return s

def page_footer():
    print("""\
    <hr>
    <p><a href="https://www.naoj.hawaii.edu/privacy/">Subaru Telescope Privacy and Logging Policy</a>
    </body>
    </html>
    """)

def upload_file(progFile, sessionValid, user_auth_type, user_auth_result, user_auth_success, user_auth_fullname, filename, file_buff, user_filetype, gsheetname):
    if progFile.error_count == 0 and (sessionValid or user_auth_success):
        input_filename = os.path.basename(filename)
        propname, ext = input_filename.split('.')

        prop_id = progFile.cfg['proposal'].proposal_info['prop_id']
        prop_dir = os.path.join(QUEUE_FILE_TOP_DIR, prop_id)

        if not os.path.exists(prop_dir):
            os.mkdir(prop_dir)

        now = datetime.datetime.now()
        out_filename = '_'.join([propname, now.strftime('%Y%m%d_%H%M%S')])
        # If the proposal ID is not already part of the filename,
        # prepend the proposal ID onto the front of the filename.
        if prop_id.upper() not in out_filename.upper():
            out_filename = '_'.join([prop_id, out_filename])
        out_filename = '.'.join([out_filename, ext])
        out_pathname = os.path.join(prop_dir, out_filename)
        with open(out_pathname, 'wb') as f:
            f.write(file_buff)
        if user_filetype == 'Google_sheet':
            successful_upload_str = 'submitted Google Sheet %s' % (gsheetname.value)
        else:
            successful_upload_str = 'uploaded File %s' % filename
        print("""\
        <h3>Successfully %s</h3>
        """ % (successful_upload_str))
        # File was successfully uploaded. Send an e-mail message to
        # HSC Queue group.
        if email_cfg.send_email_flag:
            if user_filetype == 'Google_sheet':
                input_name = gsheetname.value
            else:
                input_name = filename
            msg = email_cfg.create_msg(propname, user_auth_type, user_auth_fullname, now, user_filetype, input_name, out_pathname)
            s = smtplib.SMTP(email_cfg.smtp_server)
            logger.info('Sending e-mail about proposal %s to %s' % (propname, email_cfg.recipient))
            s.sendmail(email_cfg.sender, [email_cfg.recipient], msg.as_string())
            s.quit()
        else:
            logger.info('email_cfg.send_email_flag is %s; will not send e-mail about proposal %s' % (email_cfg.send_email_flag, propname))
    else:
        if progFile.error_count > 0:
            print("""\
            <h3><span class="%s">Error:</span> Unable to %s because error count is greater than 0</h3>
            """ % ('error', upload_err_msg[user_filetype]))
        elif not sessionValid:
            if user_auth_success is not None and not user_auth_success:
                print("""\
                <h3><span class="%s">Error:</span> Unable to %s because %s</h3>
                """ % ('error', upload_err_msg[user_filetype], user_auth_result))
            else:
                print("""\
                <h3><span class="%s">Error:</span> Unable to %s because session has expired</h3>
                """ % ('error', upload_err_msg[user_filetype]))

def report_msgs(d, severity):
    for name, l in d.items():
        for row in l:
            row_num, col_name_list, msg = row
            msg = msg.replace('<', '&lt').replace('>', '&gt')
            if row_num is None:
                print("""\
                <p>%s</p>
                """ % (msg))
            else:
                fmt = {}
                for col_name in col_name_list:
                    fmt[col_name] = lambda x: '<span class="%s">%s</span>' % (severity, ' ' if pd.isnull(x) else x)
                if row_num == 0:
                    col_names = list(progFile.df[name])
                    print("""\
                    <p>%s<br>%s</p>
                    """ % (msg, html_header(col_names, formatters=fmt)))
                else:
                    print("""\
                    <p>%s<br>%s</p>
                    """ % (msg, progFile.df[name][row_num-1:row_num].to_html(index=False, na_rep='', formatters=fmt, escape=False)))

def stars_ldap_connect(username, password):
    logger.info('STARS_LDAP_SERVER %s' % STARS_LDAP_SERVER)
    server = ldap3.Server(STARS_LDAP_SERVER, STARS_LDAP_PORT)
    loginline="uid="+username+",ou=People,dc=stars,dc=nao,dc=ac,dc=jp"
    try:
        conn = ldap3.Connection(server, loginline, password)
        login_result = conn.bind()
        if login_result:
            result="STARS Login succeeded"
            success = True
        else:
            # ldap bind fail
            result = 'STARS Login/Password Failed or Account is Locked'
            success = False

    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        # ldap server or daemon not responding
        result = 'STARS LDAP server down or not responding: %s' % str(e)
        success = False
    except Exception as e:
        result = 'Unexpected error while connecting/authenticating to STARS LDAP: %s' % str(e)
        success = False

    if success:
        conn.search(loginline, '(objectclass=person)', attributes=['gecos', 'mail'])
        e = conn.entries[0]
        userfullname = '%s (%s)' % (conn.entries[0].gecos, conn.entries[0].mail)
        logger.info('userfullname from STARS %s' % userfullname)
    else:
        userfullname = 'UNKNOWN USER'

    return result, success, userfullname

def proms_auth(id, passwd):
    # Connect to the ProMS database. Return immediately if there is a
    # problem.
    try:
        s = promsdb.ProMSdb(logger, True)
    except promsdb.ProMSdbError as e:
        result = str(e)
        success = False
        return result, success

    res, auth_check = s.user_auth_in_proms(username, password)
    logger.info('res from ProMSdb %s' % str(res))
    if auth_check:
        result="ProMS login succeeded"
        success = True
        userfullname = '%s %s (%s)' % (res.fname, res.lname, res.email)
        logger.info('userfullname from ProMSdb %s' % userfullname)
    else:
        result="ProMS ID/Password Login Failed"
        success = False
        userfullname = 'UNKNOWN USER'

    return result, success, userfullname

def createServerCookie(user_auth_type, userfullname):
    c = http.cookies.SimpleCookie()
    h = hashlib.sha1()
    h.update( repr( time.time() ).encode('utf-8') )
    sid = h.hexdigest()
    c['qcheck-session-id'] = sid
    c['qcheck-session-id']['max-age'] = COOKIE_MAX_AGE
    now = datetime.datetime.now()
    c['qcheck-session-start-timestamp'] = now.isoformat()
    end = now + datetime.timedelta(seconds=COOKIE_MAX_AGE)
    c['qcheck-session-end-timestamp'] = end.isoformat()
    c['qcheck-session-user_auth_type'] = user_auth_type
    c['qcheck-session-userfullname'] = userfullname
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
        c = http.cookies.SimpleCookie()
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

def getAttrFromCookie(c, key):
    return c[key].value

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
    logger.info('session_cookie_filepath is {}'.format(session_cookie_filepath))
    try:
        with open(session_cookie_filepath, 'rb') as f:
            serverCookie = pickle.load(f)
    except IOError:
        logger.error('Unable to open cookie pickle file %s' % session_cookie_filepath)
        return False
    logger.info('cookieFromClient is %s' % cookieFromClient)
    logger.info('serverCookie is %s' % serverCookie)
    now = datetime.datetime.now()
    qcheck_session_end_timestamp = getTimestampFromCookie(serverCookie, 'qcheck-session-end-timestamp')
    if cookieFromClient['qcheck-session-id'].value == serverCookie['qcheck-session-id'].value and now < qcheck_session_end_timestamp:
        logger.info('Session validated')
        return True
    else:
        logger.info('Session not validated')
        return False

def list_files(propid, user_filetype):
    propid_dirpath = os.path.join(QUEUE_FILE_TOP_DIR, propid)
    if os.path.isdir(propid_dirpath):
        filename_list = os.listdir(propid_dirpath)
        if len(filename_list) > 0:
            print('<hr>List of %s for Proposal ID %s:<p>' % (form_element[user_filetype]['list_caption'], propid))
            filename_list = sorted(filename_list)
            mtimes=[datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(propid_dirpath, filename))).strftime('%c') for filename in filename_list]
            sizes = [os.path.getsize(os.path.join(propid_dirpath, filename)) for filename in filename_list]
            if user_filetype == 'Excel_file':
                df = pd.DataFrame({'Filename': filename_list, 'Last Modified (HST)': mtimes, 'Size (bytes)': sizes})
            else:
                df = pd.DataFrame({'Submitted (HST)': mtimes})
            print(df.to_html(index=False, justify='center'))
        else:
            print('No files found for Proposal ID', propid)
    else:
        print('No files found for Proposal ID', propid)

logger.info('Received request from address %s' % os.environ['REMOTE_ADDR'])

form = cgi.FieldStorage()

# Check to see if the user clicked on the Logout button
try:
    logout = form['logout'].value
    sessionValid = False
except KeyError:
    logout = None

logger.info('logout value from form is {}'.format(logout))

if logout:
    logger.info('user logged out - set session to invalid')
    cc = None
    sessionValid = False
    cc = getClientCookie()
    logger.info('client cookie is {}'.format(cc))
    # Change qcheck-session-end-timestamp to a time in the past to
    # invalidate the server cookie.
    now = datetime.datetime.now()
    backdated_timestamp = now - datetime.timedelta(seconds=COOKIE_MAX_AGE)
    cc['qcheck-session-end-timestamp'] = backdated_timestamp.isoformat()
    saveCookie(cc)
else:
    # Check to see if there is a cookie in the HTTP request and if we can
    # validate the session.
    cc = getClientCookie()
    sessionValid = validateSession(cc)

if sessionValid:
    sc = cc
    user_auth_type = getAttrFromCookie(sc, 'qcheck-session-user_auth_type')
    user_auth_fullname = getAttrFromCookie(sc, 'qcheck-session-userfullname')
    logger.info('user_auth_fullname from cookie is %s' % user_auth_fullname)
else:
    user_auth_type = None
    sc = None

# Check to see if the user clicked on the Upload button
try:
    upload = form['upload'].value
except KeyError:
    upload = None

# Check to see if the user clicked on the Login button
try:
    login = form['login'].value
except KeyError:
    login = None

logger.info('login value from form is {}'.format(login))

# If upload was clicked and we weren't able to validate the session,
# see if we can validate the username/password in STARS LDAP or, if
# that fails, to ProMS MySQL database.
user_auth_success = None
user_auth_result = None
username = None
password = None
if login and not sessionValid:
    try:
        username = form['username'].value
        password = form['password'].value
    except KeyError:
        user_auth_result = 'Username/password not supplied'
    else:
        logger.info('STARS LDAP authentication for username %s' % username)
        user_auth_result, user_auth_success, user_auth_fullname = stars_ldap_connect(username, password)
        stars_ldap_result = user_auth_result
        logger.info('stars_ldap_result %s' % stars_ldap_result)
    if user_auth_success:
        logger.info('creating server cookie based on STARS LDAP user authentication')
        user_auth_type = 'STARS'
        sc = createServerCookie(user_auth_type, user_auth_fullname)
        saveCookie(sc)
        sessionValid = True
    else:
        # STARS LDAP authentication failed, try ProMS authentication
        user_auth_result, user_auth_success, user_auth_fullname = proms_auth(username, password)
        promsdb_result = user_auth_result
        logger.info('promsdb_result %s' % promsdb_result)
        if user_auth_success:
            logger.info('creating server cookie based on ProMS DB user authentication')
            user_auth_type = 'ProMS'
            sc = createServerCookie(user_auth_type, user_auth_fullname)
            saveCookie(sc)
            sessionValid = True
        else:
            sc = None

try:
    # Get file information here.
    if user_filetype == 'Excel_file':
        gsheetname = None
        fileitem = form['filename']
    elif user_filetype == 'Google_sheet':
        gsheetname = form['gsheetname']
        fileitem = None
        form_element[user_filetype]['input_prompt'] = form_element[user_filetype]['input_prompt'].replace('value=""', 'value="%s"' % gsheetname.value)
    file_info_supplied = True
except KeyError:
    file_info_supplied = False

# Check to see if the user clicked on the "List files" button
try:
    list_files_val = form['list_files'].value
    propid = form['propid'].value
except KeyError:
    list_files_val = None
    propid = ''

# HTML header and CSS information
if sessionValid:
    print(sc)
print("""\
Content-Type: text/html\n
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<meta name="Robots" content="NOINDEX,NOFOLLOW">
<meta name="Keywords" content="">
<meta name="Author" content="Russell Kackley">
<meta name="Generator" content="emacs and human">
<meta name="Copyright" content="&copy; 200X  Russell Kackley">
<title>Subaru Queue %(str1)s Checker/%(str2)s/Listing</title>
<style>
.ok      {background-color: white}
.warning {background-color: yellow}
.error   {background-color: red}
</style>
</head>
<body>
<h1>Subaru Queue %(str1)s Checker/%(str2)s/Listing</h1>
""" % title_str[user_filetype])

if user_filetype == 'Excel_file':
    print("""\
    <p>%s</p>
    <hr>
    """ % alternate_url[user_filetype])

# The form element
print("""\
<form enctype="multipart/form-data" action=%(action)s method="POST">
<input type="hidden" name="logLevel" value="30">
""" % form_element[user_filetype])
if sessionValid:
    print("""\
    %(instructions)s
    <br>
    Please enter the name of your %(file_type_str)s and then press the Check or %(button_label)s button.
    <p>
    You can also list previous %(upload_or_submit)s for a Proposal ID with the "%(list_button_label)s" button.
    <p>
    """ % form_element[user_filetype])
    print("""\
    You have already logged in as %s and your session is valid until HST %s<br>
    """ % (user_auth_fullname, getTimestampFromCookie(sc, 'qcheck-session-end-timestamp').strftime('%c')))
else:
    if login:
        print("""\
        <span class="error">Username/ID or Password incorrect. Please try again.</span>
        <p>
        """)
    print("""\
    <p>
    %(instructions)s,
    <br>
    Please enter your STARS username and password or Subaru ProMS ID and password,
    <br>
    and then press the Login button.
    <table>
    <tr>
    <td><label for="name">Userame or ID</label></td>
    <td><input type="text" name="username" id="username" value=""></td>
    </tr>
    <tr>
    <td><label for="password">Password</label></td>
    <td><input type="password" name="password" id="password" value=""></td>
    </tr>
    </table>
    <input type="submit" name="login"  value="Login">
    """ % form_element[user_filetype])
    page_footer()
    sys.exit(1)

print("""\
<hr>
%(input_prompt)s
<hr>
<br>
Check validity of your %(file_type_str)s: <input type="submit" name="check"  value="Check">
<hr>
""" % form_element[user_filetype])

print("""\
<p>
%(button_label)s your %(file_type_str)s: <input type="submit" name="upload" value="%(button_label)s">
""" % form_element[user_filetype])
print("""\
<hr>
<p>
Use the following entry field and button to list the %(list_instructions)s for a Proposal ID.
""" % form_element[user_filetype])
print("""\
<p>
<label for="name">Proposal ID</label>
<input type="text" name="propid" id="propid" value="%s"> (e.g., S22B-QN001)
""" % propid)
print("""\
<br>
<input type="submit" name="list_files" value="%(list_button_label)s">
<hr>
<input type="submit" name="logout"  value="Logout">
</form>
""" % form_element[user_filetype])

if not file_info_supplied:
    # If no file info, exit immediately
    page_footer()
    sys.exit(1)

try:
    # Get log level information here.
    logLevel = form['logLevel']
except KeyError:
    # If no logLevel, exit immediately
    page_footer()
    sys.exit(1)

# If the user selected several files, fileitem will be a
# list. Otherwise, fileitem will be a scalar. Either way set up a list
# with the contents from fileitem.
try:
    fileList = [item for item in fileitem]
except TypeError:
    fileList = [fileitem]

if user_auth_success is not None:
    if user_auth_success:
        print('STARS LDAP or ProMS DB result: %s' % user_auth_result)
    else:
        print('<h3>STARS LDAP or ProMS DB result:<br> %s <br> %s</h3>' % (stars_ldap_result, promsdb_result))

if list_files_val:
    if propid:
        if filetypes.ProposalFile.propID_re.match(propid):
            list_files(propid, user_filetype)
        else:
            print('Proposal ID %s is not valid. Please enter a valid Proposal ID, e.g., S22B-QN001.' % propid)
    else:
        print('Please enter a Proposal ID.')
    page_footer()
    sys.exit(1)

if user_filetype == 'Google_sheet':
    from pydrive.auth import GoogleAuth
    from pydrive.drive import GoogleDrive
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread
    from ginga.misc import Bunch

    JSON_FILEPATH = os.environ['GOAUTH_JSON_FILEPATH']
    SCOPE = ['https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILEPATH, SCOPE)

    print("""\
    <hr><p>Connect to Google Sheet %s</p>
    """ % (gsheetname.value))
    logger.info('Authorizing with Google OAuth2')
    gc = gspread.authorize(creds)
    logger.info('Opening Google Sheet %s' % gsheetname.value)
    try:
        gsheet = gc.open(gsheetname.value)
    except gspread.exceptions.SpreadsheetNotFound as e:
        logger.error('Error opening Google Sheet %s: %s' % (gsheetname.value, str(e)))
        print('<span class="error">Error:</span> Google Sheet %s not found' % gsheetname.value)
        page_footer()
        sys.exit(1)

    gauth = GoogleAuth()
    gauth.credentials = creds
    gdrive = GoogleDrive(gauth)
    logger.info('Create Google Drive File')
    gfile = gdrive.CreateFile({'id': gsheet.id})
    tmp_filename = os.path.join('/tmp', '%s.xlsx' % gsheetname.value)
    mimetypes = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    logger.info('Write Google Sheet to %s' % tmp_filename)
    gfile.GetContentFile(tmp_filename, mimetypes)
    logger.info('Open temp file %s' % tmp_filename)
    fh = open(tmp_filename, 'rb')
    fileList[0] = Bunch.Bunch(filename=tmp_filename, file=fh)
    logger.info('End of Google Sheet section')

if len(fileList[0].filename) > 0:

    if user_filetype == 'Excel_file':
        print('<hr>')

    for item in fileList:

        if user_filetype == 'Excel_file':
            print("""\
            <p>Reading file %s</p>
            """ % (item.filename))

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
        logger.info('type of item.filename is %s' % (item.filename))
        try:
            magic_filetype = magic.from_buffer(file_buff)
        except magic.MagicException as e:
            print("""\
            <p>Error getting magic filetype from file %s: %s</p>
            """ % (item.filename, str(e)))
            logger.error('Error getting magic filetype from file %s: %s' % (item.filename, str(e)))
        try:
            magic_type_list = magic_types[ext]
            magic_filetype_ok = False
            for t in magic_type_list:
                if t in magic_filetype:
                    magic_filetype_ok = True
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
                print("""\
                <p>%s</p>
                """ % (msg))
            if not magic_filetype_ok:
                msg = "Unexpected magic file type '%s' detected. This does not seem to be an Excel file." % (magic_filetype)
                logger.error(msg)
                print("""\
                <p>%s</p>
                """ % (msg))

        if progFile:
            if user_filetype == 'Google_sheet':
                file_check_results_str = 'Check Results from Google Sheet %s' % (gsheetname.value)
            else:
                file_check_results_str = 'File Check Results From File %s' % item.filename
            print("""\
            <h3>%s:</h3>
            """ % (file_check_results_str))
            if upload:
                upload_file(progFile, sessionValid, user_auth_type, user_auth_result, user_auth_success, user_auth_fullname, item.filename, file_buff, user_filetype, gsheetname)
            if progFile.warn_count == 0 and progFile.error_count == 0:
                print("""\
                <p><span class="ok">Error</span> count is %d</p>
                <p><span class="ok">Warning</span> count is %d</p>
                """ % (progFile.error_count, progFile.warn_count))
                print("""\
                File %s is <span class="ok">ok</span>.
                """ % (item.filename))
                if upload:
                    list_files(progFile.cfg['proposal'].proposal_info.prop_id, user_filetype)
            else:
                print("""\
                <p><span class="%s">Error</span> count is %d</p>
                """ % ('error' if progFile.error_count >0 else 'ok', progFile.error_count))
                report_msgs(progFile.errors, 'error')
                print("""\
                <p><span class="%s">Warning</span> count is %d</p>
                """ % ('warning' if progFile.warn_count >0 else 'ok', progFile.warn_count))
                report_msgs(progFile.warnings, 'warning')
                if upload and progFile.error_count == 0:
                    list_files(progFile.cfg['proposal'].proposal_info.prop_id, user_filetype)

else:
    print("""\
    <hr><p>Unable to read file - filename is empty</p>
    """)

if user_filetype == 'Google_sheet':
    if fileList[0].file:
        try:
            fileList[0].file.close()
        except Exception as e:
            pass
    try:
        logger.info('remove temp file %s' % fileList[0].filename)
        os.remove(fileList[0].filename)
    except OSError as e:
        pass

page_footer()
