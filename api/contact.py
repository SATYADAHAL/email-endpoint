from http.server import BaseHTTPRequestHandler
import json
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
import requests
import re
import logging
import textwrap
import html
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MAX_CONTENT_LENGTH = 10240  # 10KB
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
ALLOWED_ORIGINS = [
    "https://www.satyadahal.com.np",
    "https://satyadahal.com.np",
    # "http://localhost:3000"
]
ALLOWED_ENDPOINT = "/api/contact"


def is_origin_allowed(origin):
    """Check if the request origin is allowed"""
    if not origin:
        return False
    return origin in ALLOWED_ORIGINS


class handler(BaseHTTPRequestHandler):
    def send_cors_headers(self, origin, status_code=200):
        """Send CORS headers with proper origin validation"""
        self.send_response(status_code)
        if origin and is_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Type", "text/plain")
        if status_code == 200:
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        """Handle OPTIONS preflight requests"""
        origin = self.headers.get("Origin")
        self.send_cors_headers(origin, 200)

    def do_POST(self):
        """Handle POST requests to the contact form endpoint"""
        if self.path != ALLOWED_ENDPOINT:
            self.send_error(404, "Not Found")
            return

        origin = self.headers.get("Origin")
        logger.info(f"Request from Origin: {origin}")

        # Origin validation
        if not is_origin_allowed(origin):
            logger.warning(f"Blocked origin: {origin}")
            self.send_cors_headers(origin, 403)
            self.wfile.write(b"CORS policy violation")
            return

        try:
            # Content length validation
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_CONTENT_LENGTH:
                logger.warning(f"Payload too large: {content_length} bytes")
                self.send_cors_headers(origin, 413)
                self.wfile.write(b"Payload too large")
                return

            # JSON parsing
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON: {str(e)}")
                self.send_cors_headers(origin, 400)
                self.wfile.write(b"Invalid JSON format")
                return

            # reCAPTCHA verification
            recaptcha_token = data.get("g-recaptcha-response")
            if not recaptcha_token:
                logger.warning("Missing reCAPTCHA token")
                self.send_cors_headers(origin, 400)
                self.wfile.write(b"Missing reCAPTCHA token")
                return

            if not self.verify_captcha(recaptcha_token):
                logger.warning("reCAPTCHA verification failed")
                self.send_cors_headers(origin, 400)
                self.wfile.write(b"reCAPTCHA verification failed")
                return

            # Input validation
            name = data.get("name", "").strip()
            email = data.get("email", "").strip()
            message = data.get("message", "").strip()

            if not all([name, email, message]):
                logger.warning("Missing required fields")
                self.send_cors_headers(origin, 400)
                self.wfile.write(b"All fields are required")
                return

            if not re.match(EMAIL_REGEX, email):
                logger.warning(f"Invalid email format: {email}")
                self.send_cors_headers(origin, 400)
                self.wfile.write(b"Invalid email format")
                return

            # Send email
            try:
                self.send_email(name, email, message)
                logger.info(f"Email sent: {name} <{email}>")
                self.send_cors_headers(origin, 200)
                self.wfile.write(b"Message sent successfully!")
            except Exception as e:
                logger.exception("Email sending failed")
                self.send_cors_headers(origin, 500)
                self.wfile.write(b"Failed to send message")

        except Exception as e:
            logger.exception(f"Server error: {str(e)}")
            self.send_cors_headers(origin, 500)
            self.wfile.write(b"Internal server error")

    def verify_captcha(self, token):
        """Verify reCAPTCHA v2 token"""
        secret = os.environ.get("RECAPTCHA_SECRET")
        if not secret:
            logger.error("RECAPTCHA_SECRET environment variable missing")
            raise RuntimeError("reCAPTCHA configuration error")

        try:
            response = requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": secret, "response": token},
                timeout=3,
            )
            response.raise_for_status()
            result = response.json()
            logger.debug(f"reCAPTCHA result: {result}")

            if not result.get("success"):
                error_codes = result.get("error-codes", ["unknown"])
                logger.warning(f"reCAPTCHA failed: {error_codes}")
                return False

            return True
        except (requests.RequestException, ValueError) as e:
            logger.error(f"reCAPTCHA request failed: {str(e)}")
            return False

    def send_email(self, name, email, message):
        """Send formatted email with contact form submission"""
        logger.info(f"Preparing email for: {name} <{email}>")

        # Validate environment variables
        required_env = ["EMAIL_FROM", "EMAIL_TO", "EMAIL_PASSWORD"]
        if missing := [var for var in required_env if not os.environ.get(var)]:
            logger.error(f"Missing email config: {', '.join(missing)}")
            raise RuntimeError("Email configuration incomplete")

        # Create email
        msg = EmailMessage()
        msg["Subject"] = f"New Portfolio Message: {name}"
        msg["From"] = os.environ["EMAIL_FROM"]
        msg["To"] = os.environ["EMAIL_TO"]
        msg["Reply-To"] = formataddr((name, email))  # Secure header formatting

        # Create email content
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Plain text version
        plain_text = f"""\
        🚀 New Message From Your Portfolio Site

        ⏰ Received at: {timestamp}

        👤 Contact Details:
          • Name: {name}
          • Email: {email}

        📝 Message:
        {textwrap.indent(message.strip(), "    ")}

        ---
        🤖 Automated Notification - Do not reply directly to this email.
        """
        msg.set_content(textwrap.dedent(plain_text))

        # HTML version (properly escaped)
        safe_message = html.escape(message).replace("\n", "<br>")
        html_content = f"""\
        <html>
          <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
              <h2 style="color: #2563eb;">🚀 New Message From Portfolio Site</h2>
              <div style="background-color: #f3f4f6; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
                <p><strong>Received at:</strong> {timestamp}</p>
                <h3 style="color: #4b5563; margin-top: 20px;">Contact Details</h3>
                <ul>
                  <li><strong>Name:</strong> {html.escape(name)}</li>
                  <li><strong>Email:</strong> <a href="mailto:{html.escape(email)}">{html.escape(email)}</a></li>
                </ul>
                <h3 style="color: #4b5563; margin-top: 20px;">📝 Message</h3>
                <div style="white-space: pre-wrap; background: white; padding: 12px; border-radius: 4px;">
                  {safe_message}
                </div>
              </div>
              <div style="font-size: 12px; color: #6b7280; text-align: center; padding-top: 16px; border-top: 1px solid #e5e7eb;">
                <p>🔒 This message was sent securely via your portfolio contact form</p>
                <p>🤖 Automated Notification - Do not reply directly to this email</p>
              </div>
            </div>
          </body>
        </html>
        """
        msg.add_alternative(textwrap.dedent(html_content), subtype="html")

        # SMTP configuration
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 465))
        smtp_timeout = int(os.environ.get("SMTP_TIMEOUT", 10))

        # Send email
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=smtp_timeout) as smtp:
            smtp.login(os.environ["EMAIL_FROM"], os.environ["EMAIL_PASSWORD"])
            smtp.send_message(msg)
            logger.info(f"Email successfully sent via {smtp_server}:{smtp_port}")
