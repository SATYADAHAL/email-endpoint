
### Endpoints:
- Contact: POST https://email-endpoint.vercel.app/api/contact
- Test:    POST https://email-endpoint.vercel.app/api/test

### Request JSON (for /api/contact):
```env
  "name": "Your Name",
  "email": "you@example.com",
  "message": "Hello!",
  "g-recaptcha-response": "reCAPTCHA_token"
```
### Required .env variables:
```env
EMAIL_FROM=
EMAIL_TO=
EMAIL_PASSWORD=
RECAPTCHA_SECRET=
```
#### Optional .env variables:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_TIMEOUT=10
```
### CORS Allowed Origins:
- https://satyadahal.com.np
- https://www.satyadahal.com.np

## Local Setup with Vercel CLI:
1. Clone the repo:
```
   git clone git@github.com:SATYADAHAL/email-endpoint.git
   cd email-endpoint
```

2. Install Vercel CLI:
   ```npm install -g vercel```
3. Add env variables:
4. Test locally:
   ```vercel dev```

### Deploy to Vercel:
1. Login (if needed):
   vercel login

2. Deploy:
   vercel --prod
