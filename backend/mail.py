import os
import logging
import threading
from datetime import datetime
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)

mail = Mail()


def init_mail(app):
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 465
    app.config["MAIL_USE_TLS"] = False
    app.config["MAIL_USE_SSL"] = True
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = (os.environ.get("MAIL_PASSWORD") or "").replace(" ", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER")
    mail.init_app(app)


def _send_async(app, msg, on_success=None):
    with app.app_context():
        try:
            mail.send(msg)
            if on_success:
                on_success()
        except Exception as e:
            logger.error(f"Async mail send failed: {e}")


def _send(app, msg, on_success=None):
    t = threading.Thread(target=_send_async, args=(app, msg, on_success), daemon=True)
    t.start()


def send_welcome_email(patient_name, visit_type, queue_position, estimated_wait, patient_email):
    from flask import current_app
    try:
        msg = Message(
            subject="CareFlow AI - Check-In Confirmed",
            recipients=[patient_email],
            body=(
                f"Hi {patient_name},\n\n"
                f"You've been checked in for: {visit_type.replace('_', ' ')}.\n"
                f"Your current queue position is {queue_position}.\n"
                f"Estimated wait time: {estimated_wait} minutes.\n\n"
                f"We'll notify you again when you're near the front of the queue.\n\n"
                f"- CareFlow AI"
            ),
        )
        _send(current_app._get_current_object(), msg)
    except Exception as e:
        logger.error(f"Failed to send welcome email to {patient_email}: {e}")


def send_position3_email(patient_name, patient_email, on_success=None):
    from flask import current_app
    try:
        msg = Message(
            subject="CareFlow AI - You're Almost Up",
            recipients=[patient_email],
            body=(
                f"Hi {patient_name},\n\n"
                f"You're now #3 in the queue. Please make your way to the clinic "
                f"if you haven't already - you'll be called soon.\n\n"
                f"- CareFlow AI"
            ),
        )
        _send(current_app._get_current_object(), msg, on_success=on_success)
    except Exception as e:
        logger.error(f"Failed to send position-3 email to {patient_email}: {e}")


def send_booking_confirmation(patient_name, patient_email, doctor_name, slot_date, slot_time):
    from flask import current_app
    try:
        # %-d / %-I (no leading zero) are glibc/macOS strftime extensions that
        # raise on Windows, so the day/hour are stripped of zero-padding by
        # hand instead of relying on a platform-specific format code.
        date_obj = datetime.strptime(slot_date, "%Y-%m-%d")
        formatted_date = f"{date_obj.strftime('%A, %B')} {date_obj.day}, {date_obj.year}"
        time_obj = datetime.strptime(slot_time, "%H:%M")
        hour_12 = time_obj.hour % 12 or 12
        formatted_time = f"{hour_12}:{time_obj.strftime('%M %p')}"
        msg = Message(
            subject="Your CareFlow AI appointment is confirmed",
            recipients=[patient_email],
            body=(
                f"Hi {patient_name},\n\n"
                f"Your appointment at CareFlow AI Calgary Walk-In Clinic is confirmed.\n\n"
                f"Doctor: {doctor_name}\n"
                f"Date: {formatted_date}\n"
                f"Time: {formatted_time}\n\n"
                f"Please arrive 5 minutes early. Bring a valid ID and your Alberta Health Card.\n\n"
                f"If you need to cancel, please call the clinic directly.\n\n"
                f"CareFlow AI — Calgary Walk-In Clinic Platform"
            ),
        )
        _send(current_app._get_current_object(), msg)
    except Exception as e:
        logger.error(f"Failed to send booking confirmation to {patient_email}: {e}")
