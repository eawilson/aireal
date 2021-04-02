import os, pdb

from smtplib import SMTP, SMTPException
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate

__all__ = ("MailServer",)

class MailServer(object):
    
    def __init__(self, server, username=None, password=None, use_tls=True, reply_to=None, sender=None):
        """Connects to SMTP server.

        Args:
            tls (bool): Put the SMTP connection in TLS mode if True.
            kwargs (dict): Must contain username and smtp_url,
                may contain password and return_to.
            
        Returns:
            None.
            
        Raises:
            RuntimeError if username or smtp_url missing
            SMTPAuthenticationError if password incorrect.
            SMTPException for everything else
        """
        pdb.set_trace()
        self.username = username
        self.reply_to = reply_to
        self.sender = sender

        self.server = SMTP()
        self.server.connect(server)
        if use_tls:
            self.server.starttls()
        if username is not None and password is not None:
            self.server.login(username, password)

    
    def __enter__(self):
        return self

        
    def __exit__(self, tp, value, tb):
        self.close()

        
    def close(self):
        self.server.quit()

        
    def send(self, recipients, subject, body, attachments=()):
        """Sends a single email message.

        Args:
            recipients (string or list of stings): List of message recipients,
                either as a comma separated string or a list of strings.
            subject (string): Message subject.
            body (string): Message body.
            attachments (list): List of filename, content pairs
                (only .txt and .pdf filetypes supported).
            
        Returns:
            None.
            
        Raises:
            SMTPException
            RuntimeError if attachment is not .txt or .pdf
        """
        if isinstance(recipients, str):
            recipients = recipients.split(",")
        
        msg = MIMEMultipart()
        if self.sender is not None:
            msg["From"] = self.sender
        msg["To"] = ",".join(recipients)
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = subject
        if self.reply_to:
            msg.add_header("reply-to", self.reply_to)
        msg.attach(MIMEText(body))

        for filename, content in attachments:
            ext = os.path.splitext(filename)[1]
            if ext == ".txt":
                attachment = MIMEText(content)
            elif ext == ".pdf":
                    attachment = MIMEApplication(content)
            else:
                raise RuntimeError(f"Unknown email attachment type {ext}.")
            attachment.add_header("Content-Disposition", "attachment",
                                  filename=filename)
            msg.attach(attachment)

        server.send_message(msg, self.sender, recipients)
        


