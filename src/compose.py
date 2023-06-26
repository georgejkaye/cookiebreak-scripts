from email.encoders import encode_base64
from email.message import Message
from email.mime.base import MIMEBase
import os
import smtplib
import ssl
import subprocess

from icalendar import Calendar, Event, vCalAddress, vText # type: ignore
from email.utils import make_msgid, formataddr
from pathlib import Path
from time import sleep
import arrow
from typing import List, Tuple, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from structs import Break
from config import Config, debug


def write_email_template(config: Config, cookie_break: Break, template_name: str) -> str:
    current_dir = Path(__file__).resolve().parent
    templates_dir = current_dir / "templates"
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"])
    )
    template = env.get_template(template_name)
    email = template.render(cookie_break=cookie_break, admin=config.admin)
    return email


def get_announce_email_subject(cookie_break: Break) -> str:
    return f"[cookies] Cookie break this week, {cookie_break.get_short_break_date()} @ {cookie_break.get_break_time()}"


def handle_str_or_bytes(obj: Union[str, bytes]) -> str:
    if(isinstance(obj, bytes)):
        return obj.decode('UTF-8')
    return obj

def get_cookiebreak_ics_filename(next_break: Break) -> str:
    date_string = next_break.time.strftime("%Y-%m-%d")
    return f"cookiebreak-{date_string}.ics"

def create_calendar_event(config: Config, next_break: Break) -> str:
    cal = Calendar()
    cal.add('prodid', 'cookiebreaks - https://github.com/georgejkaye/cookiebreak-scripts')
    cal.add('version', '2.0')
    cal.add('method', "REQUEST")

    event = Event()
    event.add("summary", f"Cookie break: {next_break.host}")
    event.add("dtstart", next_break.time.datetime)
    event.add("dtend", next_break.time.shift(hours=1).datetime)
    event.add("dtstamp", arrow.now().datetime)
    event.add("location", next_break.location)

    organizer = vCalAddress(f"mailto:{config.admin.email}")
    organizer.params["cn"] = config.admin.fullname
    event["organizer"] = organizer

    event["uid"] = f"cookiebreak/{next_break.time.datetime}"

    for list in config.mailing_lists:
        attendee = vCalAddress(list)
        attendee.params["cutype"] = vText("GROUP")
        attendee.params["role"] = vText("REQ-PARTICIPANT")
        attendee.params["partstat"] = vText("NEEDS-ACTION")
        event.add("attendee", attendee, encode=0)
    cal.add_component(event)
    cal_text = cal.to_ical().decode()
    cal_text_fixed = cal_text.replace("BST", "Europe/London").replace("GMT", "Europe/London")
    return cal_text_fixed


def prepare_email_in_thunderbird(config: Config, next_break: Break, body: str, ics: str):
    subject = get_announce_email_subject(next_break)
    subject_item = f"subject='{subject}'"
    emails = ", ".join(config.mailing_lists)
    to_item = f"to='{emails}'"
    from_item = f"from={config.admin.email}"
    body_item = f"body='{body}'"
    attachment_item = f"attachment='{ics}'"
    plain_text_item = "format=2"
    compose_items = ",".join(
        [to_item, from_item, subject_item, body_item, plain_text_item, attachment_item])
    command = ["thunderbird", "-compose", compose_items]
    subprocess.run(command)
    window_title = f"Write: {subject} - Thunderbird"
    sleep(1)
    while True:
        wmctrl_output = str(subprocess.check_output(["wmctrl", "-l"]))
        if window_title not in wmctrl_output:
            return
        sleep(1)

def write_calendar_mime_parts(ics_content : str, ics_name: str) -> Tuple[Message, Message]:
    ics_text = MIMEText(ics_content, "calendar;method=REQUEST")
    ics_attachment = MIMEBase("text", f"calendar;name={ics_name}")
    ics_attachment.set_payload(ics_content)
    encode_base64(ics_attachment)
    return (ics_text, ics_attachment)


def write_email(sender_name: str, sender_email: str, recipients: List[str], subject: str, content: List[Message]) -> MIMEMultipart:
    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = formataddr((sender_name, sender_email))
    message["To"] = ", ".join(recipients)
    message["Message-ID"] = make_msgid()
    for item in content:
        message.attach(item)
    return message

def write_announce_email(config : Config, next_break: Break) -> MIMEMultipart:
    announce_subject = get_announce_email_subject(next_break)
    ics_content = create_calendar_event(config, next_break)
    ics_name = get_cookiebreak_ics_filename(next_break)
    email_body = MIMEText(write_email_template(config, next_break, "announce.txt"))
    (ics_text, ics_attachment) = write_calendar_mime_parts(ics_content, ics_name)
    return write_email(
        sender_name=config.admin.fullname,
        sender_email=config.admin.email,
        recipients=config.mailing_lists,
        subject=announce_subject,
        content=[email_body, ics_text, ics_attachment]
    )

def send_email(email : MIMEMultipart):
    process = subprocess.Popen(["msmtp", "--read-envelope-from", "--read-recipients"], stdin=subprocess.PIPE)
    process.communicate(email.as_bytes())

def send_announce_email(config : Config, email : MIMEMultipart):
    send_email(email)
