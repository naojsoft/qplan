#!/usr/bin/env python

import cgi, os, sys, site
import cgitb; cgitb.enable()
import logging,logging.handlers
import StringIO

LOG_FORMAT = '%(message)s'

def report_msgs(d, severity):
    for name, l in d.iteritems():
        for row in l:
            row_num, col_name_list, msg = row
            if row_num:
                fmt = {}
                for col_name in col_name_list:
                    fmt[col_name] = lambda x: '<span class="%s">%s</span>' % (severity, x)
                    print """\
                    <p>%s<br>%s</p>
                    """ % (msg, progFile.df[name][row_num-1:row_num].to_html(index=False, na_rep='', formatters=fmt, escape=False))
            else:
                print """\
                <p>%s</p>
                """ % (msg)

# HTML header and CSS information
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
<br>
<input type="submit" value="Check">
</form> 
"""

sys.path.append('/gen2/share/Git/queuesim')
site.addsitedir('/gen2/share/arch/64/lib/python')
site.addsitedir('/gen2/share/arch/64/lib/python2.7/site-packages')

import filetypes, entity

form = cgi.FieldStorage()

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

if len(fileList[0].filename) > 0:

    # Create a logger that will write to a stream/StringIO object.
    log_stream = StringIO.StringIO()
    logger = logging.Logger('qcheck_cgi')
    level = int(logLevel.value)
    fmt = logging.Formatter(LOG_FORMAT)
    logHdlr = logging.StreamHandler(log_stream)
    logHdlr.setLevel(level)
    logHdlr.setFormatter(fmt)
    logger.addHandler(logHdlr)

    for item in fileList:
        print """\
        <p>Reading file %s</p>
        """ % (item.filename)

        progFile = None
        input_filename = os.path.basename(item.filename)
        propname, ext = input_filename.split('.')
        if ext in filetypes.QueueFile.excel_ext:
            propdict = {}
            key = propname.upper()
            propdict[key] = entity.Program(key, hours=0, category='')
            progFile = filetypes.ProgramFile('', logger, propname, propdict, file_ext=ext, file_obj=item.file)
        else:
            msg = "File extension '%s' is not a valid file type. Must be one of %s." % (ext, filetypes.QueueFile.excel_ext)
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

else:
    print """\
    <p>Unable to read file - filename is empty</p>
    """

print """\
</body>
</html>
"""
