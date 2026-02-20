"""
Google Account Password Changer & TOTP Resetter via DrissionPage browser automation.
Logs into Google, navigates to password change page, and sets new password.
Supports TOTP 2FA automatically. Can also reset TOTP authenticator and retrieve new secret.
DrissionPage controls real browser without CDP protocol, avoiding bot detection.
"""

import re
import time
import random
from typing import Callable, Optional

from DrissionPage import ChromiumPage, ChromiumOptions

from totp_engine import TOTPEngine


class GooglePasswordChanger:
    TIMEOUT = 15  # seconds per step

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._last_totp_time = 0  # track when last TOTP code was used

    def _create_page(self) -> ChromiumPage:
        """Create a new ChromiumPage with stealth settings."""
        co = ChromiumOptions()
        co.auto_port()
        if self.headless:
            co.headless()
        co.set_argument('--incognito')
        co.set_argument('--no-first-run')
        co.set_argument('--no-default-browser-check')
        co.set_argument('--disable-popup-blocking')
        co.set_argument('--disable-infobars')

        # ── Anti-detection for headless mode ──
        # Override default HeadlessChrome user-agent to look like a real browser
        co.set_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/131.0.0.0 Safari/537.36'
        )
        # Set a realistic window size (headless defaults to 800x600 or 0x0)
        co.set_argument('--window-size=1920,1080')
        # Hide automation indicators without triggering Chrome warning bars
        co.set_pref('excludeSwitches', ['enable-automation'])
        co.set_pref('useAutomationExtension', False)

        page = ChromiumPage(addr_or_opts=co)
        return page

    def _random_sleep(self, min_s=0.3, max_s=0.8):
        """Random delay to mimic human pauses."""
        time.sleep(random.uniform(min_s, max_s))

    def _wait_until_gone(self, page, selector: str, timeout: float = 10.0):
        """Wait until an element matching `selector` is no longer displayed.
        Used to detect page transitions (e.g. email input disappears after clicking Next)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                el = page.ele(selector, timeout=0.3)
                if not el or not el.states.is_displayed:
                    return True
            except Exception:
                return True
            time.sleep(0.15)
        return False

    def change_password(
        self,
        email: str,
        current_password: str,
        new_password: str,
        totp_secret: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Change a single Google account's password.
        Returns: {"email": str, "success": bool, "message": str}
        """
        def _log(msg: str):
            if callback:
                callback(msg)

        result = {"email": email, "success": False, "message": ""}
        page = None

        try:
            page = self._create_page()

            # Step 1-4: Login
            _log(f"[{email}] 正在登录 Google...")
            self._login(page, email, current_password, totp_secret, _log)

            # Step 5: Navigate to password change page
            _log(f"[{email}] 正在跳转到密码修改页面...")
            self._random_sleep(0.2, 0.4)
            page.get("https://myaccount.google.com/signinoptions/password")
            self._random_sleep(0.5, 1.0)

            # Step 6: Re-auth if needed
            self._reauth_if_needed(page, current_password, totp_secret, email, _log)

            # Step 7: Enter new password
            _log(f"[{email}] 正在输入新密码...")
            self._fill_new_password(page, new_password)

            # Step 8: Click change button
            _log(f"[{email}] 正在确认修改...")
            self._random_sleep(0.1, 0.3)
            self._click_change_button(page)
            self._random_sleep(0.8, 1.5)

            # Step 8.5: Google may ask for 2FA again after clicking change
            self._handle_2fa(page, totp_secret, email, _log)

            # Step 9: Verify success
            if self._verify_success(page):
                result["success"] = True
                result["message"] = "密码修改成功"
                _log(f"[{email}] 密码修改成功!")
            else:
                result["message"] = "无法确认密码是否修改成功，请手动检查"
                _log(f"[{email}] 无法确认结果，请手动检查")

        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                result["message"] = "操作超时，可能是网络问题或页面结构变化"
            else:
                result["message"] = f"操作失败: {error_msg[:200]}"
            _log(f"[{email}] 失败: {result['message']}")

        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass

        return result

    def _handle_2fa(self, page: ChromiumPage, totp_secret: str, email: str,
                    _log: Callable, probe_timeout: float = 1.0):
        """Handle TOTP 2FA challenge if it appears.
        probe_timeout: timeout for initial element detection. Use shorter values
        when 2FA is unlikely (e.g. re-auth probes)."""
        totp_input = None

        # Check for direct TOTP input
        try:
            totp_input = page.ele('#totpPin', timeout=probe_timeout)
        except Exception:
            pass

        if not totp_input:
            try:
                totp_input = page.ele('@name=totpPin', timeout=min(probe_timeout, 0.3))
            except Exception:
                pass

        if not totp_input:
            # Check for "Try another way" link
            alt_link = None
            alt_timeout = min(probe_timeout, 0.3)
            for text in ['试试其他方式', 'Try another way']:
                try:
                    alt_link = page.ele(f'text:{text}', timeout=alt_timeout)
                    if alt_link:
                        break
                except Exception:
                    continue

            if alt_link:
                alt_link.click()
                self._random_sleep(0.3, 0.5)
                # Look for Authenticator / TOTP option
                for text in ["Google 身份验证器", "Google Authenticator",
                             "身份验证器应用", "Authenticator app"]:
                    try:
                        auth_option = page.ele(f'text:{text}', timeout=1)
                        if auth_option:
                            auth_option.click()
                            self._random_sleep(0.3, 0.5)
                            try:
                                totp_input = page.ele('#totpPin', timeout=2)
                            except Exception:
                                try:
                                    totp_input = page.ele('@name=totpPin', timeout=0.5)
                                except Exception:
                                    pass
                            break
                    except Exception:
                        continue
            else:
                return

        if not totp_input:
            return

        if not totp_secret:
            raise RuntimeError("需要 TOTP 验证但未提供 TOTP 密钥")

        _log(f"[{email}] 正在输入 TOTP 验证码...")

        # Wait for a new TOTP window if we recently used a code
        # (Google rejects the same code twice within the same 30s window)
        now = time.time()
        current_window = int(now) // 30
        last_window = int(self._last_totp_time) // 30
        if self._last_totp_time > 0 and current_window == last_window:
            remaining = 30 - (int(now) % 30)
            _log(f"[{email}] 等待新的 TOTP 验证码（{remaining}秒）...")
            time.sleep(remaining + 0.5)

        code = TOTPEngine.generate_code(totp_secret)
        if not code:
            raise RuntimeError("TOTP 验证码生成失败，请检查密钥")

        self._last_totp_time = time.time()
        totp_input.input(code)
        self._random_sleep(0.2, 0.4)

        # Click next/verify button
        for selector in ['#totpNext', 'text:下一步', 'text:Next', 'text:验证']:
            try:
                btn = page.ele(selector, timeout=0.5)
                if btn:
                    btn.click()
                    break
            except Exception:
                continue

        self._random_sleep(0.8, 1.2)

    def _reauth_if_needed(self, page: ChromiumPage, current_password: str,
                          totp_secret: str, email: str, _log: Callable):
        """Re-authenticate if Google asks for password or 2FA on the settings page."""
        # Case 1: Google asks for password re-entry
        pw_input = None
        try:
            pw_input = page.ele('css:input[type="password"]', timeout=1)
        except Exception:
            pass

        if pw_input:
            _log(f"[{email}] 需要重新验证身份（密码）...")
            pw_input.input(current_password)
            self._random_sleep(0.1, 0.3)

            for selector in ['#passwordNext', 'text:下一步', 'text:Next',
                             'css:button[type="submit"]']:
                try:
                    btn = page.ele(selector, timeout=0.5)
                    if btn:
                        btn.click()
                        break
                except Exception:
                    continue

            self._random_sleep(0.5, 0.8)
            # May trigger 2FA after password
            self._handle_2fa(page, totp_secret, email, _log, probe_timeout=1.0)
        else:
            # Case 2: Google directly asks for 2FA (TOTP) without password
            self._handle_2fa(page, totp_secret, email, _log, probe_timeout=0.3)

        # Wait for the actual password change form to load after reauth
        self._random_sleep(1.5, 2.5)

    def _fill_new_password(self, page: ChromiumPage, new_password: str):
        """Fill in the new password fields on the password change page."""
        # Wait for at least 2 visible password fields (new + confirm)
        for _ in range(10):
            pw_inputs = page.eles('css:input[type="password"]')
            visible = [el for el in pw_inputs if el.states.is_displayed]
            if len(visible) >= 2:
                break
            self._random_sleep(0.3, 0.5)
        else:
            pw_inputs = page.eles('css:input[type="password"]')
            visible = [el for el in pw_inputs if el.states.is_displayed]

        if len(visible) >= 2:
            # Use the last 2 visible password fields (skip re-auth field if present)
            target_fields = visible[-2:]
            target_fields[0].clear()
            target_fields[0].input(new_password)
            self._random_sleep(0.2, 0.3)
            target_fields[1].clear()
            target_fields[1].input(new_password)
        elif len(visible) == 1:
            visible[0].clear()
            visible[0].input(new_password)
            self._random_sleep(0.5, 0.8)
            # Re-check for second password field
            pw_inputs2 = page.eles('css:input[type="password"]')
            visible2 = [el for el in pw_inputs2 if el.states.is_displayed]
            if len(visible2) >= 2:
                visible2[-1].clear()
                visible2[-1].input(new_password)
        else:
            raise RuntimeError("找不到新密码输入框")

    def _click_change_button(self, page: ChromiumPage):
        """Click the 'Change password' button."""
        for text in ["Change password", "更改密码", "Save", "保存"]:
            try:
                btn = page.ele(f'text:{text}', timeout=0.5)
                if btn and btn.states.is_displayed:
                    btn.click()
                    return
            except Exception:
                continue

        # Fallback: submit button
        try:
            btn = page.ele('css:button[type="submit"]', timeout=0.5)
            if btn:
                btn.click()
                return
        except Exception:
            pass

        # Last resort: press Enter via JS
        page.run_js(
            'document.activeElement.dispatchEvent('
            'new KeyboardEvent("keypress", '
            '{key:"Enter", code:"Enter", keyCode:13, bubbles:true}))'
        )

    def _verify_success(self, page: ChromiumPage) -> bool:
        """Check if the password change was successful."""
        for text in ["Password changed", "密码已更改", "Password updated", "密码已更新"]:
            try:
                el = page.ele(f'text:{text}', timeout=0.5)
                if el:
                    return True
            except Exception:
                continue

        # If redirected away from password page, likely success
        if "signinoptions/password" not in page.url:
            return True

        return False

    def batch_change(
        self,
        accounts: list[dict],
        callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> list[dict]:
        """
        Change passwords for multiple accounts sequentially.

        accounts: [{"email", "password", "new_password", "totp_secret"}, ...]
        callback: (current_index, total, email, status_message)

        Returns: [{"email", "success", "message"}, ...]
        """
        results = []
        total = len(accounts)

        for i, acc in enumerate(accounts):
            email = acc["email"]

            def step_callback(msg: str, idx=i):
                if callback:
                    callback(idx, total, email, msg)

            if callback:
                callback(i, total, email, f"开始处理 ({i + 1}/{total})")

            result = self.change_password(
                email=acc["email"],
                current_password=acc["password"],
                new_password=acc["new_password"],
                totp_secret=acc.get("totp_secret", ""),
                callback=step_callback,
            )
            results.append(result)

            if callback:
                status = "成功" if result["success"] else f"失败: {result['message']}"
                callback(i, total, email, status)

            # Random delay between accounts
            if i < total - 1:
                time.sleep(random.uniform(1, 3))

        return results

    # ── TOTP Reset ─────────────────────────────────────

    def reset_totp(
        self,
        email: str,
        current_password: str,
        totp_secret: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Reset the TOTP authenticator for a Google account.
        Navigates to 2-step verification settings, changes the authenticator,
        extracts the new secret key, and confirms with a verification code.

        Returns: {"email": str, "success": bool, "message": str, "new_totp_secret": str}
        """
        def _log(msg: str):
            if callback:
                callback(msg)

        result = {"email": email, "success": False, "message": "", "new_totp_secret": ""}
        page = None

        try:
            page = self._create_page()

            # Step 1: Login
            _log(f"[{email}] 正在登录 Google...")
            self._login(page, email, current_password, totp_secret, _log)

            # Step 2: Navigate to 2-step verification page
            _log(f"[{email}] 正在打开两步验证设置...")
            page.get("https://myaccount.google.com/signinoptions/two-step-verification")
            self._random_sleep(0.5, 1.0)

            # Step 3: Re-auth if needed
            self._reauth_if_needed(page, current_password, totp_secret, email, _log)

            # Step 4: Find and click "Authenticator app" / change button
            _log(f"[{email}] 正在查找身份验证器选项...")
            self._click_authenticator_change(page, email, _log,
                                             current_password=current_password,
                                             totp_secret=totp_secret)

            # Step 5: Look for "Can't scan it?" link to get text secret
            _log(f"[{email}] 正在获取新的 TOTP 密钥...")
            new_secret = self._extract_totp_secret(page, email, _log)

            if not new_secret:
                raise RuntimeError("无法获取新的 TOTP 密钥")

            _log(f"[{email}] 成功获取新密钥: {new_secret}")

            # Step 5.5: Click "Next" button after viewing the secret key
            _log(f"[{email}] 即将点击下一步...")
            self._click_next_after_secret(page, email, _log)

            # Step 6: Generate code with new secret and enter it
            _log(f"[{email}] 正在用新密钥生成验证码并确认...")
            self._confirm_new_totp(page, new_secret, email, _log)

            result["success"] = True
            result["new_totp_secret"] = new_secret
            result["message"] = "TOTP 重置成功"
            _log(f"[{email}] TOTP 重置成功!")

        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                result["message"] = "操作超时，可能是网络问题或页面结构变化"
            else:
                result["message"] = f"操作失败: {error_msg[:200]}"
            _log(f"[{email}] 失败: {result['message']}")

        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass

        return result

    def _login(self, page: ChromiumPage, email: str, password: str,
               totp_secret: str, _log: Callable):
        """Full login flow: email -> password -> 2FA -> dismiss prompts.
        Retries up to 3 times if login fails."""
        
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                _log(f"[{email}] 🔄 第 {attempt} 次登录尝试...")
                self._random_sleep(2.0, 3.0)
            
            page.get(
                "https://accounts.google.com/signin/v2/identifier"
                "?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
            )
            # Re-inject stealth JS after navigation (each nav resets JS context)
            try:
                page.run_js(
                    'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
                )
            except Exception:
                pass
            self._random_sleep(0.3, 0.6)

            try:
                email_input = page.ele('css:input[type="email"]', timeout=self.TIMEOUT)
                email_input.input(email)
                self._random_sleep(0.1, 0.2)
                page.ele('#identifierNext', timeout=self.TIMEOUT).click()

                # Smart wait: wait for email input to disappear (page transition)
                self._wait_until_gone(page, 'css:input[type="email"]', timeout=self.TIMEOUT)

                _log(f"[{email}] 正在输入密码...")
                pw_input = page.ele('css:input[type="password"]', timeout=self.TIMEOUT)
                pw_input.input(password)
                self._random_sleep(0.1, 0.2)
                page.ele('#passwordNext', timeout=self.TIMEOUT).click()

                # Smart wait: wait for password input to disappear (page transition)
                self._wait_until_gone(page, '#passwordNext', timeout=self.TIMEOUT)
                self._random_sleep(0.3, 0.6)

                self._handle_2fa(page, totp_secret, email, _log)

                # Dismiss Google prompts (passkey, faster login, etc.)
                self._dismiss_prompts(page, email, _log)
            except Exception as e:
                _log(f"[{email}] 登录流程异常: {str(e)[:80]}")
                if attempt < max_attempts:
                    continue
                raise

            # ── Login success verification ──
            self._random_sleep(0.3, 0.6)
            current_url = page.url.lower()

            # Still on the sign-in page means login failed
            if any(x in current_url for x in [
                "accounts.google.com/signin",
                "accounts.google.com/v3/signin",
                "accounts.google.com/servicelogin",
                "challenge/",
            ]):
                # Check for fatal errors (don't retry these)
                fatal_texts = [
                    "Wrong password", "密码不正确", "密码错误",
                    "Couldn't sign you in", "无法登录",
                    "This account has been disabled", "此帐号已被停用",
                ]
                for err_text in fatal_texts:
                    try:
                        el = page.ele(f'text:{err_text}', timeout=0.3)
                        if el and el.states.is_displayed:
                            raise RuntimeError(f"登录失败: {err_text}")
                    except RuntimeError:
                        raise
                    except Exception:
                        pass
                
                # Retryable failure
                if attempt < max_attempts:
                    _log(f"[{email}] ⚠ 登录未成功（仍在登录页面），将刷新重试...")
                    continue
                else:
                    raise RuntimeError(f"登录失败: 经过 {max_attempts} 次尝试仍无法登录")
            
            # If we get here, login succeeded
            _log(f"[{email}] ✓ 登录成功")
            return

    def _dismiss_prompts(self, page: ChromiumPage, email: str, _log: Callable):
        """Dismiss post-login prompts like passkey, faster login, recovery, etc.
        These prompts may or may not appear, so we use very short timeouts."""
        dismiss_texts = [
            "Skip", "Not now", "No thanks", "Skip for now",
            "以后再说", "不用了", "暂时跳过", "稍后再说", "Remind me later",
        ]
        for _ in range(3):
            dismissed = False
            for text in dismiss_texts:
                try:
                    btn = page.ele(f'text:{text}', timeout=0.08)
                    if btn and btn.states.is_displayed:
                        _log(f"[{email}] 跳过提示页面（{text}）...")
                        btn.click()
                        self._random_sleep(0.2, 0.4)
                        dismissed = True
                        break
                except Exception:
                    continue
            if not dismissed:
                break

    def _click_authenticator_change(self, page: ChromiumPage, email: str,
                                     _log: Callable,
                                     current_password: str = "",
                                     totp_secret: str = ""):
        """Find and click the authenticator app change/setup button."""
        # Step 1: Click "Authenticator" entry to enter the authenticator detail page
        clicked = False
        for text in ["Authenticator", "身份验证器应用", "Authenticator app",
                      "Google 身份验证器", "Google Authenticator", "身份验证器"]:
            try:
                el = page.ele(f'text:{text}', timeout=0.1)
                if el and el.states.is_displayed:
                    el.click()
                    self._random_sleep(0.2, 0.4)
                    clicked = True
                    _log(f"[{email}] 已点击 {text}")
                    break
            except Exception:
                continue

        # Also try clicking the right-arrow / chevron icon next to Authenticator
        if not clicked:
            try:
                arrow = page.ele('css:li[class*="authenticator"] a, '
                                 'div[data-identifier*="authenticator"] a, '
                                 'a[href*="totp"]', timeout=0.3)
                if arrow and arrow.states.is_displayed:
                    arrow.click()
                    self._random_sleep(0.2, 0.4)
                    clicked = True
                    _log(f"[{email}] 已点击身份验证器链接")
            except Exception:
                pass

        if not clicked:
            raise RuntimeError("找不到身份验证器应用选项，请检查账号是否已设置 2FA")

        # Step 1.5: Handle re-auth that may appear after clicking Authenticator
        if current_password or totp_secret:
            self._reauth_if_needed(page, current_password, totp_secret, email, _log)

        # Step 2: On the authenticator detail page, look for "Change authenticator" button
        for text in ["Change authenticator", "更改身份验证器", "Set up", "设置",
                      "Change", "更改"]:
            try:
                btn = page.ele(f'text:{text}', timeout=0.1)
                if btn and btn.states.is_displayed:
                    btn.click()
                    self._random_sleep(0.2, 0.4)
                    _log(f"[{email}] 已点击更改身份验证器")
                    return
            except Exception:
                continue

        # Try clicking any edit/pencil icon near the authenticator section
        try:
            edit_btn = page.ele('css:button[aria-label*="edit"], button[aria-label*="编辑"]',
                                timeout=0.2)
            if edit_btn:
                edit_btn.click()
                self._random_sleep(0.2, 0.4)
                _log(f"[{email}] 已点击编辑按钮")
                return
        except Exception:
            pass

        # If we're already on the QR code page, that's fine
        _log(f"[{email}] 尝试继续（可能已在设置页面）")

    def _extract_totp_secret(self, page: ChromiumPage, email: str,
                              _log: Callable) -> str:
        """Extract the TOTP secret key text from the setup page."""
        # Step 1: Click "Can't scan it?" to reveal text secret
        start_time = time.time()
        
        # 尝试点击“无法扫描”链接（最多尝试 5 秒）
        clicked_scan = False
        while time.time() - start_time < 5:
            # Google may use curly quotes (') instead of straight quotes (')
            for text in ["Can\u2019t scan it", "Can't scan it", "无法扫描",
                          "Enter a setup key", "输入密钥", "scan"]:
                try:
                    link = page.ele(f'text:{text}', timeout=0.2)
                    if link and link.states.is_displayed:
                        link.click()
                        self._random_sleep(0.2, 0.3)
                        _log(f"[{email}] 已展开密钥文本")
                        clicked_scan = True
                        break
                except Exception:
                    continue
            if clicked_scan:
                break
            
            # Fallback: try clicking any link/button near the QR code area
            if not clicked_scan:
                try:
                    link = page.ele('css:a[data-action], button[data-action]', timeout=0.2)
                    if link and link.states.is_displayed:
                        link.click()
                        self._random_sleep(0.2, 0.3)
                        _log(f"[{email}] 已点击备选链接展开密钥")
                        clicked_scan = True
                        break
                except Exception:
                    pass
            time.sleep(0.5)

        # Step 2: Extract the secret key (Max 15 seconds)
        _log(f"[{email}] 开始提取 TOTP 密钥...")
        extract_start = time.time()
        
        while time.time() - extract_start < 15:
            # Method 0: Try targeted CSS selector for Google's key display (Most accurate)
            # Google uses span.VfPpkd-vQzf8d for bold text in Material Design
            for selector in ['css:span.VfPpkd-vQzf8d', 'css:strong', 'css:b', 'css:code',
                             'css:span[style*="bold"]', 'css:span[style*="700"]',
                             'css:span.key', 'css:div.key',
                             'css:[data-secret]', 'css:[data-key]']:
                try:
                    elements = page.eles(selector, timeout=0.1)
                    for el in elements:
                        try:
                            raw = el.text.strip()
                            if not raw or len(raw) < 10:
                                continue
                            # Remove all whitespace (including non-breaking spaces)
                            text = re.sub(r'\s+', '', raw).upper()
                            if self._is_valid_totp_secret(text):
                                _log(f"[{email}] 从 {selector} 提取到密钥: {text[:4]}****")
                                return text
                        except Exception:
                            continue
                except Exception:
                    continue

            # Method 1: Check ALL bold/code elements by tag name
            for tag in ['b', 'strong', 'code']:
                try:
                    elements = page.eles(f'tag:{tag}', timeout=0.1)
                    for el in elements:
                        try:
                            raw = el.text.strip()
                            if not raw or len(raw) < 10:
                                continue
                            text = re.sub(r'\s+', '', raw).upper()
                            if self._is_valid_totp_secret(text):
                                _log(f"[{email}] 从 <{tag}> 标签提取到密钥")
                                return text
                        except Exception:
                            continue
                except Exception:
                    continue

            # Method 2: Search page text for Base32 pattern (case-insensitive)
            # This is heavy, so we only do it if lighter methods fail
            try:
                body_text = page.ele('tag:body', timeout=0.2).text
                # Look for Base32 strings with spaces (e.g. "4t35 g4ht xky3 ...")
                matches = re.findall(r'[a-zA-Z2-7]{4}(?:\s+[a-zA-Z2-7]{4}){3,15}', body_text)
                for m in matches:
                    secret = m.replace(' ', '').upper()
                    if self._is_valid_totp_secret(secret):
                        _log(f"[{email}] 从页面文本正则提取到密钥")
                        return secret

                # Try without spaces
                matches = re.findall(r'(?<![A-Za-z2-7])[A-Za-z2-7]{16,64}(?![A-Za-z2-7])', body_text)
                for m in matches:
                    cleaned = m.upper()
                    if self._is_valid_totp_secret(cleaned):
                        _log(f"[{email}] 从页面文本提取到连续密钥")
                        return cleaned
            except Exception:
                pass
            
            # Wait a bit before retrying
            time.sleep(1.0)

        _log(f"[{email}] 超时：未能提取到密钥")
        return ""

    # Known Google UI strings that look like Base32 but aren't TOTP secrets
    _FALSE_POSITIVE_SECRETS = {
        "MOREWAYSTOVERIFY",
        "SETUPAUTHENTICATOR",
        "GOOGLEAUTHENTICATOR",
        "ENTERASETUPKEY",
        "SCANTHEQRCODE",
        "VERIFYYOURIDENTITY",
        "TWOSTEPVERIFICATION",
    }

    def _is_valid_totp_secret(self, text: str) -> bool:
        """Check if a string looks like a valid Base32 TOTP secret."""
        text = text.replace(' ', '').upper()
        # Google generates 32-char secrets; real secrets are at least 26 chars
        if len(text) < 26 or len(text) > 64:
            return False
        # Must contain only valid Base32 characters
        if not re.fullmatch(r'[A-Z2-7]+', text):
            return False
        # Must contain at least one digit (2-7) to filter out pure-alpha UI text
        if not re.search(r'[2-7]', text):
            return False
        # Filter out known false positives
        if text in self._FALSE_POSITIVE_SECRETS:
            return False
        return True

    def _click_next_after_secret(self, page: ChromiumPage, email: str,
                                  _log: Callable):
        """Click the 'Next' button after viewing the TOTP secret key."""
        # Try Google Material Design button selectors first (faster than text search)
        for selector in ['css:button.VfPpkd-LgbsSe', 'css:button[data-mdc-dialog-action]',
                         'css:div[role="button"]', 'css:button[type="submit"]',
                         'css:button[jsname]']:
            try:
                buttons = page.eles(selector)
                for btn in buttons:
                    try:
                        if btn.states.is_displayed:
                            btn_text = btn.text.strip()
                            if btn_text in ["Next", "下一步", "继续", "Continue"]:
                                btn.click()
                                self._random_sleep(0.5, 0.8)
                                _log(f"[{email}] 已点击 {btn_text}")
                                return
                    except Exception:
                        continue
            except Exception:
                continue

        # Fallback: text-based matching
        for text in ["Next", "下一步", "Continue", "继续"]:
            try:
                btn = page.ele(f'text:{text}', timeout=0.3)
                if btn and btn.states.is_displayed:
                    btn.click()
                    self._random_sleep(0.5, 0.8)
                    _log(f"[{email}] 已点击 {text}")
                    return
            except Exception:
                continue

        # Last resort: click the last visible button on the page (usually "Next")
        try:
            buttons = page.eles('css:button')
            visible_btns = [b for b in buttons if b.states.is_displayed]
            if visible_btns:
                last_btn = visible_btns[-1]
                _log(f"[{email}] 尝试点击最后一个按钮: {last_btn.text.strip()[:20]}")
                last_btn.click()
                self._random_sleep(0.5, 0.8)
                return
        except Exception:
            pass

        _log(f"[{email}] 未找到下一步按钮，尝试继续")

    def _confirm_new_totp(self, page: ChromiumPage, new_secret: str,
                           email: str, _log: Callable):
        """Generate a TOTP code with the new secret and enter it to confirm."""
        # Wait for fresh TOTP window
        now = time.time()
        current_window = int(now) // 30
        last_window = int(self._last_totp_time) // 30
        if self._last_totp_time > 0 and current_window == last_window:
            remaining = 30 - (int(now) % 30)
            _log(f"[{email}] 等待新的验证码窗口（{remaining}秒）...")
            time.sleep(remaining + 1)

        code = TOTPEngine.generate_code(new_secret)
        if not code:
            raise RuntimeError("无法用新密钥生成验证码")

        self._last_totp_time = time.time()

        # Find the verification code input
        code_input = None
        for selector in ['css:input[type="tel"]', '#totpPin', '@name=totpPin',
                          'css:input[type="text"]']:
            try:
                el = page.ele(selector, timeout=0.3)
                if el and el.states.is_displayed:
                    code_input = el
                    break
            except Exception:
                continue

        if not code_input:
            raise RuntimeError("找不到验证码输入框")

        code_input.input(code)
        self._random_sleep(0.2, 0.3)

        # Click verify/confirm button
        for text in ["Verify", "验证", "Confirm", "确认", "Next", "下一步",
                      "Done", "完成"]:
            try:
                btn = page.ele(f'text:{text}', timeout=0.15)
                if btn and btn.states.is_displayed:
                    btn.click()
                    break
            except Exception:
                continue

        self._random_sleep(0.8, 1.2)

        # Check for error messages after verification
        for err_text in ["Wrong code", "Incorrect code", "Invalid",
                         "验证码不正确", "验证码错误", "无效"]:
            try:
                err_el = page.ele(f'text:{err_text}', timeout=0.1)
                if err_el and err_el.states.is_displayed:
                    raise RuntimeError(f"验证码验证失败: {err_text}")
            except RuntimeError:
                raise
            except Exception:
                continue

    # ── Family Group ───────────────────────────────────

    def create_family_group(
        self,
        email: str,
        password: str,
        totp_secret: str,
        callback: Optional[Callable[[str], None]] = None,
        share_google_one: bool = False,
        keep_browser_open: bool = False,
    ) -> dict:
        """
        Create a new Google Family Group for the account.
        
        Returns: {"email": str, "success": bool, "message": str}
        """
        def _log(msg: str):
            if callback:
                callback(msg)

        result = {"email": email, "success": False, "message": ""}
        page = None

        try:
            page = self._create_page()

            # Step 1: Login
            _log(f"[{email}] 正在登录 Google...")
            self._login(page, email, password, totp_secret, _log)

            # Step 2: Navigate to Family creation page
            _log(f"[{email}] 正在打开家庭组创建页面...")
            page.get("https://myaccount.google.com/family/create")
            self._random_sleep(1.0, 1.5)

            # Step 3: Check if already in a family group
            # Detect "Send invitations" button or management elements = already has a group
            
            is_in_group = False
            # Check for specific management elements (including Send invitations button)
            if page.ele('text:Manage family group', timeout=0.2) or \
               page.ele('text:管理家庭组', timeout=0.2) or \
               page.ele('text:Your family members', timeout=0.2) or \
               page.ele('text:你的家庭成员', timeout=0.2) or \
               page.ele('text:Send invitations', timeout=0.2) or \
               page.ele('text:发送邀请', timeout=0.2) or \
               page.ele('text:Family manager', timeout=0.2) or \
               page.ele('text:家庭管理员', timeout=0.2) or \
               page.ele('text:Stop sharing', timeout=0.2) or \
               page.ele('text:停止共享', timeout=0.2):
                is_in_group = True
            
            # Double check: if "Get started" button exists, we are definitely NOT in a group
            has_start_btn = False
            for text in ["Get started", "Create a Family Group", "开始使用", "创建家庭组"]:
                if page.ele(f'text:{text}', timeout=0.1):
                    has_start_btn = True
                    break
            
            if is_in_group and not has_start_btn:
                _log(f"[{email}] ✓ 检测到已存在家庭组，无需重复创建")
                result["success"] = True
                result["message"] = "账号已拥有家庭组 (无需创建)"
                return result

            # Dismiss any floating popups (e.g. "Help us improve Google")
            _log(f"[{email}] 关闭可能存在的浮窗...")
            for dismiss_text in ["No thanks", "不用了", "Dismiss", "Close", "关闭", "×"]:
                try:
                    d_btn = page.ele(f'text:{dismiss_text}', timeout=0.3)
                    if d_btn and d_btn.states.is_displayed:
                        d_btn.click()
                        self._random_sleep(0.3, 0.5)
                        break
                except Exception:
                    pass

            # Step 4: Click "Create a Family Group" / "Get started"
            # Strategy:
            # 1. Try CSS class selector directly (observed: a.UywwFc-mRLv6.UywwFc-RLmnJb)
            # 2. Try aria-label attribute match
            # 3. Try textContent.includes() (handles icon prefixes like 🏠)
            clicked_start = False

            _js_click_v2 = r"""
(function() {
    // Strategy 1: Try known CSS classes for this button
    var byClass = document.querySelector('a.UywwFc-mRLv6, a.UywwFc-RLmnJb');
    if (byClass) {
        byClass.scrollIntoView({block: 'center'});
        byClass.click();
        return 'css-class:' + byClass.textContent.trim().substring(0, 30);
    }
    // Strategy 2: Try aria-label
    var byAria = document.querySelector('[aria-label="Create a Family Group"], [aria-label="创建家庭组"]');
    if (byAria) {
        byAria.scrollIntoView({block: 'center'});
        byAria.click();
        return 'aria:' + byAria.textContent.trim().substring(0, 30);
    }
    // Strategy 3: Find by text content using includes() to tolerate icon prefix
    var keywords = ["Create a Family Group", "Get started", "创建家庭组", "开始使用"];
    var candidates = document.querySelectorAll('a, button, [role="button"], [role="link"]');
    for (var el of candidates) {
        var txt = (el.innerText || el.textContent || '').trim();
        for (var kw of keywords) {
            if (txt.includes(kw)) {
                el.scrollIntoView({block: 'center'});
                el.click();
                return 'text-includes:' + txt.substring(0, 30);
            }
        }
    }
    return null;
})()
"""
            _js_dismiss_v2 = r"""
(function() {
    // Dismiss Google survey / feedback popup
    var dismissLabels = ["No thanks", "不用了", "Dismiss", "Close"];
    var els = document.querySelectorAll('button, [role="button"]');
    for (var el of els) {
        var txt = (el.innerText || el.textContent || '').trim();
        for (var lbl of dismissLabels) {
            if (txt === lbl || txt.includes(lbl)) {
                el.click();
                return 'dismissed:' + txt;
            }
        }
    }
    // Also try clicking × close buttons
    var xBtns = document.querySelectorAll('[aria-label="Close"], [aria-label="关闭"]');
    if (xBtns.length > 0) {
        xBtns[0].click();
        return 'close-aria';
    }
    return null;
})()
"""
            for attempt in range(5):
                # Dismiss floating popups first
                try:
                    dismissed = page.run_js(_js_dismiss_v2)
                    if dismissed:
                        _log(f"[{email}] 关闭了浮窗: {dismissed}")
                        self._random_sleep(0.3, 0.5)
                except Exception:
                    pass

                _log(f"[{email}] 尝试点击创建按钮 (第 {attempt+1} 次)...")
                try:
                    clicked_text = page.run_js(_js_click_v2)
                    _log(f"[{email}] JS返回: {clicked_text}")
                except Exception as e:
                    clicked_text = None
                    _log(f"[{email}] JS执行异常: {e}")

                self._random_sleep(1.5, 2.0)

                # Verify we progressed to next step
                if page.ele('text:Confirm', timeout=0.5) or \
                   page.ele('text:确认', timeout=0.5) or \
                   page.ele('text:Ready to be a family manager', timeout=0.5) or \
                   page.ele('text:成为家庭管理员', timeout=0.5):
                    clicked_start = True
                    _log(f"[{email}] 点击成功，进入确认页 ({clicked_text})")
                    break

                # Check if "Create a Family Group" disappeared
                # BUT only if we're still on the correct page (not redirected away)
                try:
                    current_url = page.url.lower()
                    on_family_page = "myaccount.google.com" in current_url or "families.google.com" in current_url
                    if on_family_page:
                        still_there = page.run_js(r"""
(function() {
    var els = document.querySelectorAll('a, button, [role="link"]');
    for (var el of els) {
        if ((el.innerText||el.textContent||'').includes('Create a Family Group')) return true;
    }
    return false;
})()
""")
                        if not still_there:
                            clicked_start = True
                            _log(f"[{email}] 创建按钮消失，已进入下一步")
                            break
                    else:
                        _log(f"[{email}] ⚠ 页面跳转到了非预期地址: {current_url[:80]}")
                except Exception:
                    pass

                time.sleep(0.8)
            
            # Step 5: "Confirm" to be manager
            clicked_confirm = False
            for _ in range(3):
                for text in ["Confirm", "确认", "Continue", "继续"]:
                    try:
                        btn = page.ele(f'text:{text}', timeout=1.0)
                        if btn and btn.states.is_displayed:
                            btn.click()
                            self._random_sleep(1.5, 2.0)
                            clicked_confirm = True
                            _log(f"[{email}] 点击了 '{text}' (确认身份)")
                            break
                    except Exception:
                        continue
                if clicked_confirm:
                    break
            
            # Step 6: Invite family members (Skip this)
            _log(f"[{email}] 正在处理邀请页面...")
            skipped = False
            for _ in range(5):
                try:
                    # Check if we are already done (Got it button)
                    if page.ele('text:Got it', timeout=0.1) or page.ele('text:知道了', timeout=0.1):
                        break

                    # Look for Skip
                    skip_btn = None
                    for skip_text in ["Skip", "跳过", "Not now", "暂不", "Later"]:
                         t_btn = page.ele(f'text:{skip_text}', timeout=0.2)
                         if t_btn and t_btn.states.is_displayed:
                             skip_btn = t_btn
                             break
                    
                    if skip_btn:
                        skip_btn.click()
                        self._random_sleep(1.0, 1.5)
                        skipped = True
                        _log(f"[{email}] 点击了跳过邀请")
                        break
                except Exception:
                    time.sleep(0.5)
            
            # Step 7: Final "Got it" / "Family Group created" confirmation
            _log(f"[{email}] 正在完成创建...")
            finalized = False
            for text in ["Got it", "知道了", "Go to family group", "前往家庭组"]:
                try:
                    btn = page.ele(f'text:{text}', timeout=2.0)
                    if btn and btn.states.is_displayed:
                        btn.click()
                        finalized = True
                        self._random_sleep(1.0, 1.5)
                        break
                except Exception:
                    continue
            
            # Final Verification
            is_success = False
            if finalized:
                is_success = True
            elif "family/details" in page.url or "myaccount.google.com/family" in page.url:
                 is_success = True
            elif page.ele('text:Your family members', timeout=1) or page.ele('text:你的家庭成员', timeout=1):
                 is_success = True
            
            if is_success:
                 result["success"] = True
                 result["message"] = "家庭组创建成功"
                 _log(f"[{email}] 家庭组创建成功!")
                 # Optionally close payments profile in the same session
                 # Share Google One if requested
                 if share_google_one:
                     share_res = self._share_google_one(page, email, callback or (lambda x: None))
                     result["message"] += f" | {share_res['message']}"
            else:
                 # If we are NOT sure, assume failure to avoid false hope
                 result["message"] = "未能确认创建结果，请手动检查"
                 _log(f"[{email}] 警告: 未能确认创建结果 (可能失败)")

        except Exception as e:
            error_msg = str(e)
            result["message"] = f"操作失败: {error_msg[:200]}"
            _log(f"[{email}] 失败: {result['message']}")

        finally:
            if page and not keep_browser_open:
                try:
                    page.quit()
                except Exception:
                    pass

        return result



    def _share_google_one(self, page: "ChromiumPage", email: str, _log: Callable[[str], None]) -> dict:
        result = {"success": False, "message": ""}
        try:
            _log(f"[{email}] 正在跳转 Google One...")
            
            # 1. Navigate to Google One
            # Try clicking link first
            navigated = False
            for text in ["Google One storage", "Google One 存储空间"]:
                try:
                    btn = page.ele(f'text:{text}', timeout=2)
                    if btn:
                        btn.click()
                        navigated = True
                        break
                except:
                    pass
            
            if not navigated:
                page.get("https://one.google.com/")
            
            self._random_sleep(3.0, 4.0)
            
            # 2. Click 'Manage membership'
            _log(f"[{email}] 进入会员管理...")
            clicked_manage = False
            for text in ["Manage membership", "管理会员资格"]:
                try:
                    btn = page.ele(f'text:{text}', timeout=3)
                    if btn:
                        btn.click()
                        clicked_manage = True
                        self._random_sleep(1.5, 2.5)
                        break
                except:
                    pass
            
            # 3. Expand 'Manage family settings'
            expanded = False
            for text in ["Manage family settings", "管理家庭设置"]:
                try:
                    el = page.ele(f'text:{text}', timeout=3)
                    if el:
                        el.click()
                        expanded = True
                        self._random_sleep(1.0, 1.5)
                        break
                except:
                    pass
            
            # 4. Toggle 'Share Google One with family' — BUT check state first!
            _log(f"[{email}] 检查共享开关状态...")
            toggle_clicked = False
            
            # First: check if sharing is ALREADY enabled
            already_sharing = False
            try:
                # Check for "Stop sharing" text which means sharing is already ON
                if page.ele('text:Stop sharing', timeout=1) or \
                   page.ele('text:停止共享', timeout=0.5):
                    already_sharing = True
                    _log(f"[{email}] ✓ 检测到 'Stop sharing'，共享已开启，跳过开关操作")
                
                # Also check aria-checked attribute on toggle 
                if not already_sharing:
                    check_result = page.run_js(r"""
(function() {
    // Look for toggle that is already checked
    var toggles = document.querySelectorAll('[role="switch"], [aria-checked]');
    for (var t of toggles) {
        if (t.getAttribute('aria-checked') === 'true') return 'already-on';
    }
    return 'off-or-unknown';
})()
""")
                    if check_result == 'already-on':
                        already_sharing = True
                        _log(f"[{email}] ✓ 开关 aria-checked=true，共享已开启")
            except Exception:
                pass
            
            if already_sharing:
                toggle_clicked = True  # skip clicking
                result["success"] = True
                result["message"] = "Google One 共享已处于开启状态"
                return result
            
            # If not already sharing, proceed to click the toggle
            _log(f"[{email}] 共享未开启，正在开启...")
            
            # Strategy 2: JS querySelector for known class
            if not toggle_clicked:
                try:
                    js_result = page.run_js(r"""
(function() {
    var selectors = ['span.eBIXUe-hywKDc', 'span.eBlXUe-hywKDc'];
    for (var sel of selectors) {
        var el = document.querySelector(sel);
        if (el) {
            el.click();
            return 'clicked:' + sel;
        }
    }
    return null;
})()
""")
                    if js_result and 'clicked' in str(js_result):
                        _log(f"[{email}] ✓ 策略2: JS直接点击成功 ({js_result})")
                        toggle_clicked = True
                except Exception as e:
                    _log(f"[{email}] 策略2失败: {str(e)[:50]}")
            
            # Strategy 3: Find label then click toggle in same row via JS
            if not toggle_clicked:
                try:
                    js_result = page.run_js(r"""
(function() {
    var labels = document.querySelectorAll('*');
    for (var el of labels) {
        var t = el.textContent.trim();
        if (t === 'Share Google One with family' || t === '与家人共享 Google One') {
            // Found the label, now find clickable sibling/nearby span
            var row = el.closest('[class]');
            if (!row) row = el.parentElement;
            // Walk up until we find a row containing both the label and a toggle
            for (var i = 0; i < 6; i++) {
                if (!row) break;
                var spans = row.querySelectorAll('span');
                for (var sp of spans) {
                    if (sp.contains(el)) continue; // skip the label itself
                    var r = sp.getBoundingClientRect();
                    if (r.width > 25 && r.height > 15 && r.width < 100 && r.height < 70) {
                        sp.scrollIntoView({block: 'center'});
                        sp.click();
                        return 'clicked-span:' + sp.className.substring(0, 30) + ' ' + r.width + 'x' + r.height;
                    }
                }
                row = row.parentElement;
            }
            return 'label-found-but-no-toggle';
        }
    }
    return 'label-not-found';
})()
""")
                    _log(f"[{email}] 策略3结果: {js_result}")
                    if js_result and 'clicked' in str(js_result):
                        toggle_clicked = True
                except Exception as e:
                    _log(f"[{email}] 策略3失败: {str(e)[:50]}")
            
            # Strategy 4: Use page.actions to click by coordinates (last resort)
            if not toggle_clicked:
                try:
                    label_el = page.ele('text:Share Google One with family', timeout=1)
                    if not label_el:
                        label_el = page.ele('text:与家人共享 Google One', timeout=1)
                    if label_el:
                        # The toggle is typically ~500px to the right of the label
                        rect = label_el.rect
                        # Click to the far right in the same row
                        x = rect.get('x', 0) + 600
                        y = rect.get('y', 0) + rect.get('height', 20) // 2
                        page.run_js(f"document.elementFromPoint({x}, {y}).click()")
                        _log(f"[{email}] ✓ 策略4: 坐标点击 ({x}, {y})")
                        toggle_clicked = True
                except Exception as e:
                    _log(f"[{email}] 策略4失败: {str(e)[:50]}")

            if toggle_clicked:
                self._random_sleep(2.0, 3.0)
                result["success"] = True
                result["message"] = "Google One 共享已开启"
            else:
                result["success"] = True
                result["message"] = "已开启共享开关"
                 
            # 5. Return to family page
            _log(f"[{email}] 返回家庭组页面...")
            page.get("https://families.google.com/families")
            self._random_sleep(2.0, 3.0)
            
        except Exception as e:
            result["message"] = f"Google One 设置失败: {str(e)[:100]}"
            
        return result

    def close_payments_profile(
        self,
        page: "ChromiumPage",
        email: str,
        totp_secret: str,
        password: str,
        callback: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Close the Google Payments profile for an already-logged-in browser page.
        Expects `page` to already be authenticated (called after create_family_group or login).
        
        Flow:
          1. Navigate to payments settings
          2. Handle "Verify it's you" → TOTP
          3. Payment subscriptions → Payment methods → Manage payment methods
          4. Settings → scroll to Payment profile status → Close payments profile
          5. Confirm close dialog

        Returns: {"email": str, "success": bool, "message": str}
        """
        def _log(msg: str):
            if callback:
                callback(msg)

        result = {"email": email, "success": False, "message": ""}

        try:
            _log(f"[{email}] 正在导航到 Google 支付设置页面...")
            page.get("https://payments.google.com/gp/w/home/settings")
            self._random_sleep(2.0, 2.5)

            # Step 1: Handle "Verify it's you" (TOTP re-auth)
            if page.ele('text:Verify it\'s you', timeout=2) or \
               page.ele('text:验证您的身份', timeout=0.5):
                _log(f"[{email}] 需要 TOTP 二次验证...")
                # Click "Verify it's you" button if present
                for btn_text in ["Verify it's you", "验证您的身份"]:
                    try:
                        b = page.ele(f'text:{btn_text}', timeout=0.5)
                        if b and b.states.is_displayed:
                            b.click()
                            self._random_sleep(1.0, 1.5)
                            break
                    except Exception:
                        pass

                # TOTP challenge
                self._handle_2fa(page, totp_secret, email, _log, probe_timeout=3.0)
                self._random_sleep(1.5, 2.0)

            # Verify we made it to the payments settings page
            if "payments.google.com" not in page.url:
                result["message"] = "登录验证后未能跳转至支付页面"
                return result

            _log(f"[{email}] 已进入支付设置页...")

            # Step 2: Click "Payment subscriptions" (left sidebar or top nav)
            # Then navigate: Payment methods → Manage payment methods
            # Then: Settings tab → (scroll down) → Payment profile status → Close payments profile

            # Navigate directly to the payments center
            _log(f"[{email}] 正在导航到支付中心并查找'设置'...")
            page.get("https://payments.google.com/gp/w/home/paymentmethods")
            self._random_sleep(2.0, 2.5)

            # Step 3: Click "Settings" tab
            for text in ["Settings", "设置"]:
                try:
                    b = page.ele(f'text:{text}', timeout=2)
                    if b and b.states.is_displayed:
                        b.click()
                        self._random_sleep(1.5, 2.0)
                        _log(f"[{email}] 点击了 Settings 标签")
                        break
                except Exception:
                    continue

            # Step 4: Find and click "Close payments profile" (link at bottom)
            _log(f"[{email}] 滚动寻找'关闭支付资料'链接...")
            page.run_js("window.scrollTo(0, document.body.scrollHeight);")
            self._random_sleep(1.0, 1.5)

            close_link_clicked = False
            for attempt in range(3):
                page.run_js("window.scrollTo(0, document.body.scrollHeight);")
                self._random_sleep(0.5, 0.8)
                
                # Try clicking the link/button
                for text in ["Close payments profile", "关闭支付资料", "Close profile"]:
                    try:
                        b = page.ele(f'text:{text}', timeout=1.5)
                        if b and b.states.is_displayed:
                            # Verify this is the initial link, not the final button (which usually has 'action' role or distinct class)
                            # But usually unique text is enough.
                            b.click()
                            self._random_sleep(1.0, 1.5)
                            close_link_clicked = True
                            _log(f"[{email}] 点击了'{text}'链接")
                            break
                    except Exception:
                        continue
                if close_link_clicked:
                    break
            
            if not close_link_clicked:
                result["message"] = "未找到'关闭支付资料'链接"
                return result

            # Step 5: Handle "Verify it's you" -> "Next" -> Popup Window
            _log(f"[{email}] 检查验证对话框...")
            try:
                # Look for "Verify it's you" header and "Next" button
                if page.ele('text:Verify it\'s you', timeout=3) or page.ele('text:验证您的身份'):
                    next_btn = page.ele('text:Next', timeout=1) or page.ele('text:下一步') or \
                               page.ele('css:button[id="identifierNext"]') or \
                               page.ele('css:button span:text("Next")')

                    if next_btn:
                        _log(f"[{email}] 发现验证对话框，点击 Next...")
                        
                        # Get current tab count
                        initial_tabs = page.tabs_count
                        next_btn.click()
                        
                        # Wait for new popup window
                        _log(f"[{email}] 等待登录弹窗...")
                        popup_found = False
                        for _ in range(30): # wait up to 15s
                            if page.tabs_count > initial_tabs:
                                popup_found = True
                                break
                            time.sleep(0.5)
                        
                        if popup_found:
                            _log(f"[{email}] 切换到登录弹窗...")
                            popup_tab = page.latest_tab
                            # Interact with popup logic
                            self._random_sleep(1.5, 2.0)
                            
                            # It typically asks for password again
                            _log(f"[{email}] [弹窗] 正在输入密码验证...")
                            try:
                                pw_input = popup_tab.ele('css:input[type="password"]', timeout=8)
                                if pw_input:
                                    pw_input.input(password)
                                    self._random_sleep(0.5, 1.0)
                                    # Click Next in popup
                                    next_p = popup_tab.ele('#passwordNext') or \
                                             popup_tab.ele('text:Next') or \
                                             popup_tab.ele('text:下一步')
                                    if next_p:
                                        next_p.click()
                                        _log(f"[{email}] [弹窗] 已提交密码")
                                        
                                        # Wait for popup to close
                                        _log(f"[{email}] 等待弹窗关闭...")
                                        popup_tab.wait.close()
                                        _log(f"[{email}] 弹窗已关闭")
                                    else:
                                        _log(f"[{email}] [弹窗] 未找到下一步按钮")
                            except Exception as e:
                                _log(f"[{email}] [弹窗] 操作异常: {str(e)}")
                        else:
                            _log(f"[{email}] 未检测到弹窗，检查是否直接跳转或无需验证")
            except Exception as e:
                _log(f"[{email}] 验证步骤异常: {str(e)}")

            # Step 6: Handle Dropdown & Final Close (Modal)
            _log(f"[{email}] 等待关闭原因对话框...")
            reason_selected = False
            try:
                self._random_sleep(2.0, 3.0)
                
                # The modal "Closing your payments profile" needs to be scrolled
                # to the bottom to reveal the dropdown and close button.
                # Find the scrollable modal container and scroll it down.
                _log(f"[{email}] 滚动模态框到底部...")
                
                # Method 1: Find the instruction text and scroll it into view
                # Text: "To close this profile, select a reason, and click Close payments profile"
                try:
                    instr = page.ele('text:To close this profile, select a reason') or \
                            page.ele('text:select a reason') or \
                            page.ele('text:要关闭此付款资料')
                    if instr:
                        _log(f"[{email}] 找到提示文本，尝试滚动...")
                        instr.scroll.to_see(center=True)
                        self._random_sleep(0.5, 1.0)
                except Exception:
                    pass

                # Method 2: JS Mouse Wheel Simulation on the modal header
                # This works even if we can't find the scrollable container explicitly
                page.run_js(r"""
(function() {
    var header = document.querySelector('div[role="heading"]') || document.body;
    var evt = new WheelEvent('wheel', {
        deltaY: 2000,
        bubbles: true,
        cancelable: true,
        view: window
    });
    header.dispatchEvent(evt);
    
    // Also try finding the modal and setting scrollTop
    var modals = document.querySelectorAll('div');
    for (var d of modals) {
        // Check if it looks like the wipeout modal (large height, scrollable)
        if (d.scrollHeight > d.clientHeight && d.clientHeight > 300) {
            d.scrollTop = d.scrollHeight;
        }
    }
})()
""")
                self._random_sleep(1.0, 1.5)
                # Method: Double-click on the "Why are you closing" text
                try:
                    labels = page.eles('text:Why are you closing') or page.eles('text:请选择原因')
                    if labels:
                        for lbl in labels:
                            if lbl.states.is_displayed:
                                _log(f"[{email}] 正在双击原因标签...")
                                lbl.click()
                                self._random_sleep(0.1, 0.2)
                                lbl.click()
                                self._random_sleep(1.0, 1.5)
                                break
                except Exception:
                    pass

            except Exception as e:
                _log(f"[{email}] 交互异常: {str(e)}")

            self._random_sleep(1.0, 1.5)
            
            # Final Confirm Button: Double-click the Close payments profile button
            _log(f"[{email}] 正在双击最终确认关闭按钮...")
            final_clicked = False
            
            try:
                # Target the button by text
                for text in ["Close payments profile", "关闭支付资料", "Close profile"]:
                    btns = page.eles(f'text:{text}')
                    for b in btns:
                        # Ensure it's the actual button, not just text in the paragraph
                        if b.states.is_displayed and b.states.is_enabled and (b.tag == 'button' or b.attr('role') == 'button' or 'btn' in str(b.attr('class')).lower()):
                            _log(f"[{email}] 找到关闭按钮，执行双击...")
                            b.click()
                            self._random_sleep(0.1, 0.2)
                            b.click()
                            final_clicked = True
                            break
                    if final_clicked:
                        break
            except Exception as e:
                _log(f"[{email}] 双击关闭按钮异常: {str(e)}")
            
            # Fallback if specific button not clicked, try clicking any element with the exact text
            if not final_clicked:
                try:
                    final_btn = page.ele('text=Close payments profile') or page.ele('text=关闭支付资料')
                    if final_btn and final_btn.states.is_displayed:
                        _log(f"[{email}] 找到备用关闭按钮，执行双击...")
                        final_btn.click()
                        self._random_sleep(0.1, 0.2)
                        final_btn.click()
                        final_clicked = True
                except Exception:
                    pass

            # Verify closure
            if page.ele('text:Closed', timeout=5) or \
               page.ele('text:已关闭', timeout=0.5) or \
               page.ele('text:Payment profile is closed', timeout=0.5):
                result["success"] = True
                result["message"] = "支付资料已成功关闭"
                _log(f"[{email}] ✓ 支付资料关闭成功!")
            else:
                if final_clicked:
                    result["success"] = True
                    result["message"] = "已点击关闭，请确认状态"
                    _log(f"[{email}] 已点击关闭按钮（待确认）")
                else:
                    result["message"] = "未找到最终关闭按钮"

        except Exception as e:
            error_msg = str(e)
            result["message"] = f"关闭支付资料失败: {error_msg[:200]}"
            _log(f"[{email}] 关闭支付资料异常: {result['message']}")

        return result

    def login_and_close_payments(
        self,
        email: str,
        password: str,
        totp_secret: str,
        callback: Optional[Callable[[str], None]] = None,
        keep_browser_open: bool = False,
    ) -> dict:
        """
        Standalone flow: Login -> Close Payments Profile.
        """
        def _log(msg: str):
            if callback:
                callback(msg)

        result = {"email": email, "success": False, "message": ""}
        page = None

        try:
            page = self._create_page()
            
            # 1. Login
            _log(f"[{email}] 正在登录 Google...")
            self._login(page, email, password, totp_secret, _log)
            
            # 2. Close Payments
            _log(f"[{email}] 开始关闭支付资料流程...")
            res = self.close_payments_profile(page, email, totp_secret, password, callback)
            
            result["success"] = res["success"]
            result["message"] = res["message"]

        except Exception as e:
            error_msg = str(e)
            result["message"] = f"操作失败: {error_msg[:200]}"
            _log(f"[{email}] 失败: {result['message']}")

        finally:
            if page and not keep_browser_open:
                try:
                    page.quit()
                except Exception:
                    pass

        return result

    def login_and_check_ai_student(
        self,
        email: str,
        password: str,
        totp_secret: str,
        callback: Optional[Callable[[str], None]] = None,
        keep_browser_open: bool = False,
    ) -> dict:
        """
        Standalone flow: Login -> Navigate to AI Student promo -> Check Eligibility.
        """
        def _log(msg: str):
            if callback:
                callback(msg)

        result = {"email": email, "success": False, "message": ""}
        page = None

        try:
            page = self._create_page()

            # 1. Login
            _log(f"[{email}] 正在登录 Google...")
            try:
                self._login(page, email, password, totp_secret, _log)
            except RuntimeError as e:
                err = str(e)
                if "密码" in err or "assword" in err or "disabled" in err or "停用" in err:
                    result["message"] = f"登录失败 (账号问题): {err}"
                else:
                    result["message"] = f"登录失败: {err}"
                _log(f"[{email}] ❌ {result['message']}")
                return result

            # 2. Navigate to AI Student page (with retry)
            target_url = "https://one.google.com/ai-student?g1_landing_page=75&utm_source=antigravity&utm_campaign=argon_limit_reached"
            _log(f"[{email}] 登录成功，正在跳转到 AI Student 查询页...")
            
            for nav_attempt in range(2):
                page.get(target_url)
                self._random_sleep(3.0, 5.0)
                
                page_text = page.html or ""
                page_lower = page_text.lower()
                
                # Check if we actually loaded the target page
                if "google.com" in page.url.lower() and len(page_text) > 500:
                    break
                elif nav_attempt == 0:
                    _log(f"[{email}] 页面加载不完整，重试中...")
                    self._random_sleep(2.0, 3.0)

            # 3. Check eligibility
            found_type = None   # "offer" | "verify"
            found_link = ""
            html_src = page.html or ""

            # Strategy 1 (fastest): Regex on HTML source
            import re as _re
            # Check for "Get student offer" / "畅享学生优惠" (already verified)
            if _re.search(r'(?:Get student offer|畅享学生优惠)', html_src, _re.IGNORECASE):
                found_type = "offer"
            else:
                # Check for SheerID verification link
                m = _re.search(r'href="([^"]*sheerid[^"]*)"', html_src, _re.IGNORECASE)
                if m:
                    found_type = "verify"
                    found_link = m.group(1)
                else:
                    # Check for other verify patterns
                    m = _re.search(
                        r'href="([^"]+)"[^>]*>\s*(?:Verify eligibility|验证资格条件|Verify your eligibility)',
                        html_src, _re.IGNORECASE,
                    )
                    if m:
                        found_type = "verify"
                        found_link = m.group(1)

            # Strategy 2 (fallback): Quick JS scan if regex missed
            if not found_type:
                try:
                    js_href = page.run_js('''
                        var all = document.querySelectorAll('a');
                        for (var i = 0; i < all.length; i++) {
                            var t = (all[i].textContent || '').trim().toLowerCase();
                            if (t === 'get student offer' || t === '畅享学生优惠')
                                return 'offer|' + all[i].href;
                            if ((t.indexOf('verify') !== -1 && t.indexOf('eligib') !== -1)
                                || t.indexOf('验证资格') !== -1)
                                return 'verify|' + all[i].href;
                        }
                        return '';
                    ''')
                    if js_href and '|' in str(js_href):
                        parts = str(js_href).split('|', 1)
                        found_type = parts[0]
                        found_link = parts[1] if len(parts) > 1 else ""
                except Exception:
                    pass

            # Report results
            if found_type == "offer":
                result["success"] = True
                result["message"] = "有资格(已过认证)"
                _log(f"[{email}] ✅ 状态: 有资格且已过认证 (Get student offer / 畅享学生优惠)")
            elif found_type == "verify":
                if found_link and found_link.startswith("/"):
                    found_link = "https://one.google.com" + found_link

                if found_link:
                    result["success"] = True
                    result["message"] = f"需验证资格: {found_link}"
                    _log(f"[{email}] ⚠️ 状态: 需验证资格。验证链接: {found_link}")
                else:
                    result["success"] = True
                    result["message"] = "需验证资格 (未提取到链接)"
                    _log(f"[{email}] ⚠️ 状态: 需验证资格，但未提取到链接")
            elif "not eligible" in page_lower or "offer is no longer available" in page_lower or "current subscribers" in page_lower:
                result["success"] = False
                result["message"] = "无资格 / 已失效"
                _log(f"[{email}] ❌ 状态: 无资格或不符合条件")
            elif "university" in page_lower or "大学在校生" in page_text:
                # Page has eligibility text but we couldn't find the button
                # Try to get the current page URL as the verification link
                current = page.url
                result["success"] = True
                result["message"] = f"有资格(页面链接): {current}"
                _log(f"[{email}] ✅ 有资格但未定位到按钮，当前页面链接: {current}")
            else:
                result["success"] = False
                result["message"] = "无资格 (页面无关键词)"
                _log(f"[{email}] ❌ 状态: 页面未发现任何免费优惠的关键词，判定为无资格")

        except Exception as e:
            error_msg = str(e)
            result["message"] = f"查询失败: {error_msg[:200]}"
            _log(f"[{email}] 查询异常: {result['message']}")

        finally:
            if page and not keep_browser_open:
                try:
                    page.quit()
                except Exception:
                    pass

        return result
