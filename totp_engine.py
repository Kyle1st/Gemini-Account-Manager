import time
import re

import pyotp


class TOTPEngine:
    @staticmethod
    def generate_code(secret: str) -> str:
        """Return current 6-digit TOTP code for the given base32 secret."""
        if not secret:
            return ""
        try:
            cleaned = re.sub(r"\s+", "", secret).upper()
            totp = pyotp.TOTP(cleaned)
            return totp.now()
        except Exception:
            return ""

    @staticmethod
    def get_remaining_seconds() -> int:
        """Return seconds remaining in current 30-second TOTP window."""
        return 30 - (int(time.time()) % 30)

    @staticmethod
    def validate_secret(secret: str) -> bool:
        """Check if a string is a valid base32 TOTP secret."""
        if not secret:
            return False
        try:
            cleaned = re.sub(r"\s+", "", secret).upper()
            pyotp.TOTP(cleaned).now()
            return True
        except Exception:
            return False

    @staticmethod
    def clean_secret(secret: str) -> str:
        """Strip spaces and uppercase the secret."""
        return re.sub(r"\s+", "", secret).upper()

    @staticmethod
    def generate_secret() -> str:
        """Generate a random base32 TOTP secret."""
        return pyotp.random_base32()
