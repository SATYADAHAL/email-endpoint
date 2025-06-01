from http.server import BaseHTTPRequestHandler
import json
import os
import smtplib
from email.message import EmailMessage
import requests
import re
import logging
import textwrap
import html
from datetime import datetime


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 10240  # 10KB
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class handler(BaseHTTPRequestHandler):
    def set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "text/plain")
        if status_code == 200:
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self.set_headers(200)

    def do_POST(self):
        try:
            # Validate content length
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_CONTENT_LENGTH:
                logger.warning("Payload too large: %d bytes", content_length)
                self.set_headers(413)
                self.wfile.write(b"Payload too large")
                return

            # Read and parse JSON
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON: %s", str(e))
                self.set_headers(400)
                self.wfile.write(b"Invalid JSON format")
                return

            # Validate reCAPTCHA token
            recaptcha_token = data.get("g-recaptcha-response")
            if not recaptcha_token:
                logger.warning("Missing reCAPTCHA token")
                self.set_headers(400)
                self.wfile.write(b"Missing reCAPTCHA token")
                return

            # Verify reCAPTCHA
            try:
                if not self.verify_captcha(recaptcha_token):
                    logger.warning("reCAPTCHA verification failed")
                    self.set_headers(400)
                    self.wfile.write(b"reCAPTCHA verification failed")
                    return
            except Exception as e:
                logger.exception("reCAPTCHA verification error")
                self.set_headers(500)
                self.wfile.write(b"Internal server error during reCAPTCHA verification")
                return

            # Validate input fields
            name = data.get("name", "").strip()
            email = data.get("email", "").strip()
            message = data.get("message", "").strip()

            if not all([name, email, message]):
                logger.warning("Missing required fields")
                self.set_headers(400)
                self.wfile.write(b"All fields are required")
                return

            # Validate email format
            if not re.match(EMAIL_REGEX, email):
                logger.warning("Invalid email format: %s", email)
                self.set_headers(400)
                self.wfile.write(b"Invalid email format")
                return

            # Send email
            try:
                self.send_email(name, email, message)
                logger.info("Email sent successfully for: %s <%s>", name, email)
                self.set_headers(200)
                self.wfile.write(b"Message sent successfully!")
            except Exception as e:
                logger.exception("Email sending failed")
                self.set_headers(500)
                self.wfile.write(b"Failed to send message")

        except Exception as e:
            logger.exception("Unexpected server error")
            self.set_headers(500)
            self.wfile.write(b"Internal server error")

    def verify_captcha(self, token):
        secret = os.environ.get("RECAPTCHA_SECRET")
        if not secret:
            raise RuntimeError("RECAPTCHA_SECRET environment variable missing")

        try:
            response = requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": secret, "response": token},
                timeout=5,
            )
            response.raise_for_status()
            result = response.json()
            logger.debug("reCAPTCHA verification result: %s", result)
            return bool(result.get("success"))
        except (requests.RequestException, ValueError) as e:
            logger.error("reCAPTCHA request failed: %s", str(e))
            raise RuntimeError("reCAPTCHA service error") from e

    def send_email(self, name, email, message):
        logger.info("Preparing email for: %s <%s>", name, email)

        # Validate environment variables
        env_vars = ["EMAIL_FROM", "EMAIL_TO", "EMAIL_PASSWORD"]
        if any(os.environ.get(var) is None for var in env_vars):
            raise RuntimeError("Missing email configuration in environment variables")

        # Create email with professional formatting
        msg = EmailMessage()
        msg["Subject"] = f"New Portfolio Message: {name}"
        msg["From"] = os.environ["EMAIL_FROM"]
        msg["To"] = os.environ["EMAIL_TO"]
        msg["Reply-To"] = f"{name} <{email}>"

        # Formatted email body with clear structure
        email_body = f"""\
        🚀 New Message From Your Portfolio Site
        
        ⏰ Received at: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
        
        👤 Contact Details:
          • Name: {name}
          • Email: {email}
        
        📝 Message:
        {textwrap.indent(message.strip(), "    ")}
    
        ---
        🔒 This message was sent securely via your portfolio contact form.
        🤖 Automated Notification - Do not reply directly to this email.
        """

        msg.set_content(email_body)
        msg.add_alternative(
            f"""\
        <html>
          <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
              <h2 style="color: #2563eb;">🚀 New Message From Your Portfolio Site</h2>
              
              <div style="background-color: #f3f4f6; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
                <p><strong>⏰ Received at:</strong> {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
                
                <h3 style="color: #4b5563; margin-top: 20px;">👤 Contact Details</h3>
                <ul>
                  <li><strong>Name:</strong> {name}</li>
                  <li><strong>Email:</strong> <a href="mailto:{email}">{email}</a></li>
                </ul>
                
                <h3 style="color: #4b5563; margin-top: 20px;">📝 Message</h3>
                <div style="white-space: pre-wrap; background: white; padding: 12px; border-radius: 4px;">
                  {html.escape(message).replace("\n", "<br>")}
                </div>
              </div>
              
              <div style="font-size: 12px; color: #6b7280; text-align: center; padding-top: 16px; border-top: 1px solid #e5e7eb;">
                <p>🔒 This message was sent securely via your portfolio contact form</p>
                <p>🤖 Automated Notification - Do not reply directly to this email</p>
              </div>
            </div>
          </body>
        </html>
        """,
            subtype="html",
        )

        # SMTP configuration
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 465))
        smtp_timeout = int(os.environ.get("SMTP_TIMEOUT", 10))

        with smtplib.SMTP_SSL(
            host=smtp_server, port=smtp_port, timeout=smtp_timeout
        ) as smtp:
            smtp.login(
                user=os.environ["EMAIL_FROM"], password=os.environ["EMAIL_PASSWORD"]
            )
            smtp.send_message(msg)
