"""Account security primitives used by the EBL HTTP server.
"""
import datetime
import hashlib
import hmac
import secrets

from ebl_config import AGE_REQUIREMENT

def registration_age_eligible(value, minimum_age=AGE_REQUIREMENT):
    """Validate 13+ eligibility without persisting the submitted birth date."""
    try:
        dob=datetime.date.fromisoformat(str(value or "").strip())
    except Exception:
        return False
    today=datetime.datetime.now(datetime.timezone.utc).date()
    if dob>today:
        return False
    try:
        cutoff=today.replace(year=today.year-int(minimum_age))
    except ValueError:
        cutoff=today.replace(year=today.year-int(minimum_age),day=28)
    return dob<=cutoff


def pwhash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    dk=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),200_000)
    return salt+"$"+dk.hex()
















def pwcheck(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            200_000
        )
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, AttributeError, TypeError):
        return False
