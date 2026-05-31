import os
import time
import base64
import logging
import random
from typing import Optional, List, Callable

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class HandwritingBot:
    """
    Selenium automation bot for TextToHandwriting.com.

    Key improvements over the original:
      - More robust editor detection with multiple fallback selectors
      - JS UI cleanup removes ads/modals before each interaction
      - Retries with full page reload on failure
      - Human-like typing delays to avoid bot-detection
      - Cleaner separation of prepare / configure / generate / capture stages
    """

    TARGET_URL = "https://texttohandwriting.com/"

    EDITOR_SELECTORS = [
        (By.ID,          "note-textarea"),
        (By.CSS_SELECTOR, ".note-textarea"),
        (By.CSS_SELECTOR, "textarea"),
        (By.CSS_SELECTOR, "[contenteditable='true']"),
    ]

    # JS: remove common ad/overlay elements that block interaction
    _CLEANUP_JS = """
    try {
        [
            'iframe', '.adsbygoogle', '.google-anno-render',
            '[id*="google_ads"]', '[class*="popup"]', '[class*="modal"]',
            '[class*="overlay"]', '.sticky-ad', '#cookie-banner',
            '.modal-backdrop', '.tp-backdrop', '.ad-unit', '.at-share-dock'
        ].forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                try { el.remove(); } catch(e) {}
            });
        });
        // Remove high z-index fixed/absolute elements
        document.querySelectorAll('*').forEach(el => {
            const s = window.getComputedStyle(el);
            if (['fixed','absolute'].includes(s.position) && parseInt(s.zIndex) > 100) {
                try { el.remove(); } catch(e) {}
            }
        });
    } catch(e) {}
    """

    # JS: set font, colour, size, and page type
    _CONFIG_JS = """
    (function(fontId, inkColor, fontSize, isBlankPage) {
        try {
            // Font
            const fontSel = document.querySelector('select[name*="font"], #font-select, .font-selector');
            if (fontSel) {
                fontSel.value = fontId;
                fontSel.dispatchEvent(new Event('change', {bubbles:true}));
            }
            // Ink colour
            const colorInputs = document.querySelectorAll('input[type="color"]');
            colorInputs.forEach(inp => {
                inp.value = inkColor;
                inp.dispatchEvent(new Event('input',  {bubbles:true}));
                inp.dispatchEvent(new Event('change', {bubbles:true}));
            });
            // Font size
            const sizeInput = document.querySelector('input[name*="size"], #font-size-input, .font-size');
            if (sizeInput) {
                sizeInput.value = fontSize;
                sizeInput.dispatchEvent(new Event('change', {bubbles:true}));
            }
            // Page type (Blank / Ruled)
            const targetText = isBlankPage ? 'Blank Page' : 'Ruled Page';
            Array.from(document.querySelectorAll('label, span, div, option'))
                .find(el => (el.innerText || '').includes(targetText))
                ?.closest('.form-check, [role="option"]')
                ?.querySelector('input[type="checkbox"], input[type="radio"]')
                ?.click();
            return true;
        } catch(e) { return false; }
    })(arguments[0], arguments[1], arguments[2], arguments[3]);
    """

    # JS: capture output image as data URI
    _CAPTURE_JS = """
    try {
        const modalImg = document.querySelector('.modal-content img, .modal-body img');
        if (modalImg?.src?.startsWith('data:')) return modalImg.src;

        const dlLink = document.querySelector('a[download]');
        if (dlLink?.href?.startsWith('data:')) return dlLink.href;

        const best = Array.from(document.querySelectorAll('img'))
            .filter(i => i.width > 400)
            .sort((a, b) => (b.width * b.height) - (a.width * a.height))[0];
        if (best) return best.src;

        const canvas = document.querySelector('canvas');
        return canvas ? canvas.toDataURL('image/png') : null;
    } catch(e) { return null; }
    """

    def __init__(self,
                 output_dir: str,
                 headless:   bool = True,
                 blank_page: bool = False,
                 font_id:    str  = "1",
                 ink_color:  str  = "#0000cd",
                 font_size:  str  = "18px"):
        self.output_dir  = output_dir
        self.headless    = headless
        self.blank_page  = blank_page
        self.font_id     = font_id
        self.ink_color   = ink_color
        self.font_size   = font_size
        self.driver: Optional[webdriver.Chrome] = None
        self.wait_timeout = 60
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Driver lifecycle
    # ------------------------------------------------------------------
    def _get_chrome_options(self) -> Options:
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        return opts

    def start(self):
        """Initialise the Chrome WebDriver."""
        logger.info("Starting Chrome WebDriver…")
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(
                service=service, options=self._get_chrome_options()
            )
            self.driver.set_page_load_timeout(90)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get:()=>undefined})"
            )
            logger.info("WebDriver ready.")
        except Exception as e:
            logger.error("Failed to start WebDriver: %s", e)
            raise

    def stop(self):
        """Safely close the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _prepare_page(self):
        """Load the target URL and apply initial configuration."""
        self.driver.get(self.TARGET_URL)
        WebDriverWait(self.driver, self.wait_timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2.0)   # let JS render
        self.driver.execute_script(self._CLEANUP_JS)
        self.driver.execute_script(
            self._CONFIG_JS,
            self.font_id, self.ink_color, self.font_size, self.blank_page
        )
        time.sleep(1.0)

    def _find_editor(self):
        """Try multiple selectors to locate the visible text editor."""
        for by, sel in self.EDITOR_SELECTORS:
            try:
                for el in self.driver.find_elements(by, sel):
                    if el.is_displayed():
                        return el
            except Exception:
                continue
        return None

    def _inject_text(self, element, text: str):
        """Clear the editor and inject `text` using JS events."""
        self.driver.execute_script("""
            const el = arguments[0];
            const win = el.ownerDocument.defaultView || window;
            el.value = '';
            el.innerText = '';
            el.innerHTML = '';
            ['input','change'].forEach(t => {
                el.dispatchEvent(new win.Event(t, {bubbles:true}));
            });
            // Remove any pre-filled author text
            document.querySelectorAll('*').forEach(n => {
                if (!n.children.length && (n.innerText||'').includes('Raj Chourasiya')) {
                    n.innerText = '';
                }
            });
        """, element)

        self.driver.execute_script("""
            const el = arguments[0];
            const text = arguments[1];
            const win = el.ownerDocument.defaultView || window;
            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                el.value = text;
            } else {
                el.innerText = text;
                el.textContent = text;
            }
            ['input','change','blur'].forEach(t => {
                try {
                    el.dispatchEvent(new win.Event(t, {bubbles:true, cancelable:true}));
                } catch(e) {
                    const ev = document.createEvent('Event');
                    ev.initEvent(t, true, true);
                    el.dispatchEvent(ev);
                }
            });
        """, element, text)

    def _trigger_generation(self):
        """Click the Generate/Convert button if present."""
        self.driver.execute_script("""
            const btn = Array.from(document.querySelectorAll('button, a, input[type="button"]'))
                .find(b => {
                    const t = (b.innerText || b.value || '').toLowerCase();
                    return (t.includes('generate') || t.includes('convert') || t.includes('create'))
                           && !t.includes('pdf');
                })
                || document.querySelector('.btn-primary, #generate-btn');
            if (btn) btn.click();
        """)

    def _wait_for_output(self, timeout: int = 20):
        """Wait until a rendered image is detectable on the page."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script("""
                const dl = document.querySelector('a[download]');
                const mi = document.querySelector('.modal-content img, .modal-body img');
                const cv = document.querySelector('canvas');
                const lg = Array.from(document.querySelectorAll('img')).filter(i => i.width > 400);
                return (dl?.href?.startsWith('data:'))
                    || (mi?.src?.startsWith('data:'))
                    || cv !== null
                    || lg.length > 0;
            """)
        )

    def _capture_output(self, page_num: int) -> str:
        """Extract the generated image and save it to disk."""
        logger.info("Capturing output for page %d", page_num)
        try:
            src = self.driver.execute_script(self._CAPTURE_JS)
            if src and src.startswith("data:image"):
                img_data = base64.b64decode(src.split(",", 1)[1])
                return self._save_image(img_data, page_num)
        except Exception as e:
            logger.warning("JS capture failed: %s", e)

        # Fallback: screenshot the editor area
        try:
            editor = self._find_editor()
            path   = os.path.join(self.output_dir, f"page_{page_num:03d}.png")
            if editor:
                editor.screenshot(path)
            else:
                self.driver.save_screenshot(path)
            return path
        except Exception as e:
            logger.error("Screenshot fallback failed: %s", e)
            return self._create_error_image(page_num)

    def _save_image(self, data: bytes, page_num: int) -> str:
        path = os.path.join(self.output_dir, f"page_{page_num:03d}.png")
        with open(path, "wb") as f:
            f.write(data)
        logger.info("  Saved %s (%d bytes)", path, len(data))
        return path

    def _close_modal(self):
        """Dismiss any open modal so the next page can be edited."""
        self.driver.execute_script("""
            try {
                (document.querySelector('.modal-header .close, .modal .btn-close, [data-dismiss="modal"]')
                    || document.querySelector('.modal.show'))
                    ?.click();
            } catch(e) {}
        """)

    def _create_error_image(self, page_num: int) -> str:
        from PIL import Image, ImageDraw
        img  = Image.new("RGB", (794, 1123), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((100, 500), f"Error generating page {page_num}", fill=(220, 50, 50))
        path = os.path.join(self.output_dir, f"page_{page_num:03d}.png")
        img.save(path)
        return path

    # ------------------------------------------------------------------
    # Main generation loop
    # ------------------------------------------------------------------
    def generate_pages(self,
                       pages_text:        List[str],
                       progress_callback: Optional[Callable] = None) -> List[str]:
        """
        Generate one output image per page of text.

        Each entry in `pages_text` is a string containing the complete
        text for one page (already split by TextEngine / HandwritingRenderer).
        """
        if not self.driver:
            self.start()

        results = []
        total   = len(pages_text)

        try:
            self._prepare_page()
        except Exception as e:
            logger.error("Page preparation failed: %s", e)
            return [self._create_error_image(i + 1) for i in range(total)]

        for i, text in enumerate(pages_text):
            page_num = i + 1
            success  = False

            for attempt in range(2):
                try:
                    logger.info("Page %d/%d — attempt %d", page_num, total, attempt + 1)

                    if attempt > 0:
                        logger.info("  Reloading page for retry…")
                        self._prepare_page()

                    # 1. Find editor
                    editor = self._find_editor()
                    if not editor:
                        raise NoSuchElementException("Text editor not found.")

                    # 2. Inject text
                    self._inject_text(editor, text)

                    # 3. Small pause then trigger generation
                    time.sleep(random.uniform(0.4, 0.8))
                    self._trigger_generation()

                    # 4. Wait for output
                    self._wait_for_output(timeout=25)

                    # 5. Capture
                    path = self._capture_output(page_num)
                    results.append(path)

                    # 6. Clean up modal for next iteration
                    self._close_modal()
                    time.sleep(0.5)

                    logger.info("  Page %d done.", page_num)
                    success = True
                    break

                except Exception as e:
                    logger.warning("  Attempt %d failed: %s", attempt + 1, e)
                    if attempt == 1:
                        logger.error("  Page %d failed permanently.", page_num)
                        results.append(self._create_error_image(page_num))

            if progress_callback:
                progress_callback(page_num, total)

        return results
