import imaplib
import ssl
import email
import re
import asyncio
from database import cur, db
from config import logger

def get_imap_credentials():
    r_user = cur.execute("SELECT value FROM settings WHERE key='gmail_user'").fetchone()
    r_pass = cur.execute("SELECT value FROM settings WHERE key='gmail_pass'").fetchone()
    user = r_user[0] if r_user and r_user[0] else "vinitgodaragodara3@gmail.com"
    pwd = r_pass[0] if r_pass and r_pass[0] else "dqwo agxp srsw fdax"
    return user, pwd

def _sync_verify_utr(utr_query):
    email_user, email_pass = get_imap_credentials()
    if not email_user or not email_pass:
        return False, "IMAP email credentials not configured in settings."

    utr_clean = utr_query.strip()
    if len(utr_clean) < 6:
        return False, "Invalid UTR / Transaction ID length."

    try:
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=context)
        mail.login(email_user, email_pass)
        mail.select("INBOX")

        # Search by TEXT
        status, data = mail.search(None, f'(TEXT "{utr_clean}")')
        if status != "OK" or not data or not data[0]:
            mail.logout()
            return False, "Payment notification not found in email inbox."

        mail_ids = data[0].split()
        # Check matching emails starting from most recent
        for m_id in reversed(mail_ids[-5:]):
            status, msg_data = mail.fetch(m_id, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    body = ""
                    if msg.is_multipart():
                        for p in msg.walk():
                            payload = p.get_payload(decode=True)
                            if payload:
                                body += payload.decode(errors="ignore") + " "
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode(errors="ignore")

                    clean_text = re.sub("<[^<]+?>", " ", body)
                    clean_text = re.sub(r"\s+", " ", clean_text)

                    if utr_clean.lower() in clean_text.lower():
                        # Extract amount (e.g. received ₹35.0 or ₹35)
                        amt_match = re.search(r"received\s*₹\s*([0-9]+(?:\.[0-9]+)?)", clean_text, re.I)
                        if not amt_match:
                            amt_match = re.search(r"₹\s*([0-9]+(?:\.[0-9]+)?)", clean_text)
                        
                        amt = float(amt_match.group(1)) if amt_match else 0.0
                        
                        # Extract sender
                        sender_match = re.search(r"from\s+([^.]+?)\s*(?:\.|\sat|\swith)", clean_text, re.I)
                        sender = sender_match.group(1).strip() if sender_match else "User"

                        mail.logout()
                        return True, {
                            "utr": utr_clean,
                            "amount": int(amt) if amt == int(amt) else amt,
                            "sender": sender,
                            "raw": clean_text[:200]
                        }

        mail.logout()
        return False, "UTR found in inbox but transaction details could not be parsed."
    except Exception as e:
        logger.error(f"IMAP verification exception: {e}")
        return False, f"IMAP Error: {str(e)}"

async def verify_payment_utr(utr_query):
    """Asynchronous wrapper for IMAP payment verification."""
    return await asyncio.to_thread(_sync_verify_utr, utr_query)
