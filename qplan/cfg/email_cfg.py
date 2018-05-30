#
# E-mail configuration for sending a message when a user
# successfully uploads a file to the hscq server.
#
#  Russell Kackley (rkackley@naoj.org)
#

import socket
from email.mime.text import MIMEText

send_email_flag = True

# Our SMTP server is defined here
smtp_server = 'smtp.subaru.nao.ac.jp'

sender_name = 'hscq.web.check'
server_name = socket.getfqdn()
sender = '@'.join([sender_name, server_name])

recipient = 'queue@naoj.org'

mail_str = {'Excel_file': 'uploaded',
            'Google_sheet': 'submitted',
            }

def create_msg(propname, user_auth_type, user_auth_fullname, upload_datetime, user_filetype, input_name, fullpathname):

    body = 'An HSC Queue spreadsheet for proposal %s was %s to the hscq server by %s user %s on %s. Input was %s named %s. Output filename is %s:%s' % (propname, mail_str[user_filetype], user_auth_type, user_auth_fullname, upload_datetime.strftime('%c'), user_filetype, input_name, server_name, fullpathname)
    subject = 'HSC Queue spreadsheet for %s was %s' % (propname, mail_str[user_filetype])
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    return msg
