import json
import os
import uuid
import copy
from datetime import datetime


TAG_OPTIONS = ["家庭组", "成品号", "资格号"]


class AccountManager:
    def __init__(self, data_file: str = None):
        if data_file is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            data_file = os.path.join(base_dir, "accounts_data.json")
        self.data_file = data_file
        self.accounts: list[dict] = []
        self.load()

    def load(self) -> None:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.accounts = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.accounts = []
        else:
            self.accounts = []

    def save(self) -> None:
        tmp_file = self.data_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self.accounts, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, self.data_file)

    def add_account(self, email: str, password: str,
                    recovery_email: str = "", totp_secret: str = "",
                    notes: str = "", tags: list[str] | None = None) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        account = {
            "id": uuid.uuid4().hex,
            "email": email,
            "password": password,
            "recovery_email": recovery_email,
            "totp_secret": totp_secret,
            "notes": notes,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
        }
        self.accounts.append(account)
        self.save()
        return copy.deepcopy(account)

    def update_account(self, account_id: str, **fields) -> dict | None:
        for acc in self.accounts:
            if acc["id"] == account_id:
                for key, value in fields.items():
                    if key == "tags":
                        acc["tags"] = value
                    elif key in ("cookies", "cookie_updated_at"):
                        acc[key] = value
                    elif key in acc and key not in ("id", "created_at"):
                        acc[key] = value
                acc["updated_at"] = datetime.now().isoformat(timespec="seconds")
                self.save()
                return copy.deepcopy(acc)
        return None

    def save_cookies(self, email: str, cookies: list[dict]) -> bool:
        """Save cookies for an account identified by email."""
        for acc in self.accounts:
            if acc["email"] == email:
                acc["cookies"] = cookies
                acc["cookie_updated_at"] = datetime.now().isoformat(timespec="seconds")
                self.save()
                return True
        return False

    def get_cookies(self, email: str) -> list[dict] | None:
        """Get saved cookies for an account. Returns None if no cookies."""
        for acc in self.accounts:
            if acc["email"] == email:
                cookies = acc.get("cookies")
                if cookies:
                    return copy.deepcopy(cookies)
                return None
        return None

    def clear_cookies(self, email: str) -> bool:
        """Clear saved cookies for an account."""
        for acc in self.accounts:
            if acc["email"] == email:
                acc.pop("cookies", None)
                acc.pop("cookie_updated_at", None)
                self.save()
                return True
        return False

    def delete_account(self, account_id: str) -> bool:
        for i, acc in enumerate(self.accounts):
            if acc["id"] == account_id:
                self.accounts.pop(i)
                self.save()
                return True
        return False

    def get_account(self, account_id: str) -> dict | None:
        for acc in self.accounts:
            if acc["id"] == account_id:
                return copy.deepcopy(acc)
        return None

    def get_all_accounts(self, sort_by: str = "created") -> list[dict]:
        if sort_by == "created":
            # Import order: keep original list order
            return copy.deepcopy(self.accounts)
        sorted_accounts = sorted(self.accounts, key=lambda a: a["email"].lower())
        return copy.deepcopy(sorted_accounts)

    def search_accounts(self, query: str, sort_by: str = "created") -> list[dict]:
        q = query.lower()
        results = [
            acc for acc in self.accounts
            if q in acc["email"].lower() or q in acc.get("recovery_email", "").lower()
        ]
        if sort_by == "email":
            results.sort(key=lambda a: a["email"].lower())
        return copy.deepcopy(results)

    @staticmethod
    def parse_batch_line(line: str) -> dict | None:
        """Parse 'email----password----recovery_email----totp_secret' format."""
        line = line.strip()
        if not line:
            return None
        parts = line.split("----")
        if not parts[0]:
            return None
        return {
            "email": parts[0].strip(),
            "password": parts[1].strip() if len(parts) > 1 else "",
            "recovery_email": parts[2].strip() if len(parts) > 2 else "",
            "totp_secret": parts[3].strip() if len(parts) > 3 else "",
        }

    @staticmethod
    def format_line(acc: dict) -> str:
        """Format account as 'email----password----recovery_email----totp_secret'."""
        return "----".join([
            acc.get("email", ""),
            acc.get("password", ""),
            acc.get("recovery_email", ""),
            acc.get("totp_secret", ""),
        ])
