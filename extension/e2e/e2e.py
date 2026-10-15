"""Headless end-to-end test of the built extension against the real Supabase project.

Build first (`npm run build:firefox` / `npm run build` in extension/), then from the repo root:
    uv run --no-project --with selenium --with python-dotenv --with requests \
        python extension/e2e/e2e.py . firefox        # or: chrome
Needs SUPABASE_SERVICE_ROLE_KEY in the root .env: it creates a throwaway confirmed user and
deletes it (rows cascade) at the end. Firefox uses /Applications/Firefox.app; Chrome uses
Chrome for Testing, which Selenium downloads (branded Chrome ignores --load-extension).
Screenshots land in extension/e2e/shots-<browser>/ (gitignored).
"""
import json, pathlib, secrets, sys, time, traceback, uuid
import requests
from dotenv import dotenv_values
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select

ROOT = pathlib.Path(sys.argv[1]).resolve()
BROWSER = sys.argv[2] if len(sys.argv) > 2 else "firefox"
OUT = pathlib.Path(__file__).parent / f"shots-{BROWSER}"
OUT.mkdir(exist_ok=True)

root_env = dotenv_values(ROOT / ".env")
ext_env = dotenv_values(ROOT / "extension/.env.local")
URL = ext_env["WXT_SUPABASE_URL"].rstrip("/")
SERVICE = root_env["SUPABASE_SERVICE_ROLE_KEY"]
ADMIN = {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}"}

GH_CONFIRM = "https://job-boards.greenhouse.io/anthropic/jobs/4461450008/confirmation"
GH_EMBED = "https://job-boards.greenhouse.io/embed/job_app/confirmation?for=anthropic&token=4461450008"
GECKO_ID = "primora@primora.app"
EXT_UUID = str(uuid.uuid4())

results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def rows(user_id):
    r = requests.get(f"{URL}/rest/v1/job_applications", headers=ADMIN,
                     params={"user_id": f"eq.{user_id}", "select": "company,role,status,source,posting_key,url"})
    r.raise_for_status()
    return r.json()


def wait_for(fn, timeout=15, step=0.5):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(step)
    return last if last else None


def make_driver():
    if BROWSER == "firefox":
        opts = webdriver.FirefoxOptions()
        opts.add_argument("-headless")
        opts.binary_location = "/Applications/Firefox.app/Contents/MacOS/firefox"
        # Fixed moz-extension:// UUID so we can open the popup page directly.
        opts.set_preference("extensions.webextensions.uuids", json.dumps({GECKO_ID: EXT_UUID}))
        from selenium.webdriver.firefox.service import Service
        d = webdriver.Firefox(options=opts, service=Service(service_args=["--allow-system-access"]))
        d.install_addon(str(ROOT / "extension/.output/firefox-mv3"), temporary=True)
        return d, f"moz-extension://{EXT_UUID}"
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.browser_version = "stable"  # Chrome for Testing; branded Chrome ignores --load-extension
    opts.add_argument(f"--load-extension={ROOT / 'extension/.output/chrome-mv3'}")
    opts.add_argument("--enable-unsafe-extension-debugging")
    d = webdriver.Chrome(options=opts)
    # Find the extension id from its service worker target.
    d.get("chrome://extensions")
    ext_id = None
    for _ in range(20):
        targets = d.execute_cdp_cmd("Target.getTargets", {})["targetInfos"]
        sw = [t for t in targets if t["type"] == "service_worker" and t["url"].startswith("chrome-extension://")]
        if sw:
            ext_id = sw[0]["url"].split("/")[2]
            break
        time.sleep(0.5)
    if not ext_id:
        raise RuntimeError("extension service worker not found")
    return d, f"chrome-extension://{ext_id}"


def toast_present(d):
    return d.execute_script("return !!document.querySelector('[data-primora-toast]')")


MAIN = {}


def open_popup(d, base):
    """Popup page in its own fresh tab (Marionette refuses web page -> moz-extension:// navigations)."""
    close_popup(d)
    MAIN.setdefault("handle", d.current_window_handle)
    d.switch_to.new_window("tab")
    url = f"{base}/popup.html"
    if BROWSER == "firefox":
        # Load it from the browser chrome with the system principal.
        with d.context(d.CONTEXT_CHROME):
            d.execute_script(
                "Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser"
                ".fixupAndLoadURIString(arguments[0], {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});",
                url)
        WebDriverWait(d, 10).until(lambda x: x.current_url.startswith(base))
    else:
        d.get(url)


def close_popup(d):
    if "handle" in MAIN and d.current_window_handle != MAIN["handle"]:
        d.close()
        d.switch_to.window(MAIN["handle"])


def popup_eval(d, base, js):
    """Run async JS in an extension page (has the `browser`/`chrome` API)."""
    open_popup(d, base)
    WebDriverWait(d, 10).until(lambda x: x.execute_script("return document.readyState") == "complete")
    out = d.execute_async_script(
        "const done = arguments[arguments.length-1];"
        "const api = globalThis.browser ?? globalThis.chrome;"
        f"(async () => {{ {js} }})().then(done, e => done('ERR ' + e));"
    )
    close_popup(d)
    return out


def main():
    email = f"primora-test-{secrets.token_hex(4)}@example.com"
    password = secrets.token_urlsafe(16)
    r = requests.post(f"{URL}/auth/v1/admin/users", headers=ADMIN,
                      json={"email": email, "password": password, "email_confirm": True})
    r.raise_for_status()
    user_id = r.json()["id"]
    print("throwaway user created", flush=True)
    d = None
    try:
        d, base = make_driver()
        d.set_script_timeout(20)
        print("extension base:", base, flush=True)

        # 1. Signed out: confirmation page queues the log, toast + badge count.
        d.get(GH_CONFIRM)
        check("signed-out: toast on Greenhouse confirmation", wait_for(lambda: toast_present(d)))
        d.save_screenshot(str(OUT / "1-signed-out-toast.png"))
        q = popup_eval(d, base, "const g = await api.storage.local.get('primora:pending-logs'); return g['primora:pending-logs'] ?? [];")
        check("signed-out: log queued in storage", isinstance(q, list) and len(q) == 1, str(q)[:160])
        badge = popup_eval(d, base, "return await api.action.getBadgeText({});")
        check("signed-out: badge shows queue count", badge == "1", f"badge={badge!r}")

        # 2. Sign in through the popup; queue flushes.
        open_popup(d, base)
        WebDriverWait(d, 10).until(lambda x: x.find_elements(By.CSS_SELECTOR, "input[type=email]"))
        d.find_element(By.CSS_SELECTOR, "input[type=email]").send_keys(email)
        d.find_element(By.CSS_SELECTOR, "input[type=password]").send_keys(password)
        d.find_element(By.XPATH, "//button[normalize-space()='Sign in']").click()
        signed = wait_for(lambda: email in d.find_element(By.TAG_NAME, "body").text)
        check("popup: email sign-in shows the account", signed)
        got = wait_for(lambda: rows(user_id))
        check("queue synced after sign-in", got and len(got) == 1, json.dumps(got)[:200])
        if got:
            check("row enriched from Greenhouse API",
                  got[0]["company"] == "Anthropic" and got[0]["source"] == "greenhouse" and got[0]["role"],
                  f"{got[0]['company']} / {got[0]['role']}")
        d.save_screenshot(str(OUT / "2-popup-signed-in.png"))
        badge = popup_eval(d, base, "return await api.action.getBadgeText({});")
        check("badge cleared after sync", badge == "", f"badge={badge!r}")

        # 3. Signed in: revisit = duplicate guard.
        close_popup(d)
        d.get(GH_CONFIRM)
        check("duplicate: toast on revisit", wait_for(lambda: toast_present(d)))
        time.sleep(2)
        check("duplicate guard: still one row", len(rows(user_id)) == 1)
        badge = popup_eval(d, base, "return await api.action.getBadgeText({});")
        check("duplicate: badge flashes '='", badge == "=", f"badge={badge!r}")

        # 4. Embedded Greenhouse inside a company page (iframe, all_frames).
        requests.delete(f"{URL}/rest/v1/job_applications", headers=ADMIN, params={"user_id": f"eq.{user_id}"}).raise_for_status()
        close_popup(d)
        d.get("https://example.com/")  # stands in for a company career page
        d.execute_script(
            "document.body.innerHTML = '';"
            "const f = document.createElement('iframe'); f.id = 'gh'; f.src = arguments[0];"
            "f.style.width = '800px'; f.style.height = '600px'; document.body.appendChild(f);", GH_EMBED)
        got = wait_for(lambda: rows(user_id), timeout=20)
        check("embedded iframe: logged with signed-in session", got and len(got) == 1, json.dumps(got)[:200])
        d.switch_to.frame(d.find_element(By.ID, "gh"))
        check("embedded iframe: toast inside the frame", wait_for(lambda: toast_present(d)))
        d.switch_to.default_content()
        d.save_screenshot(str(OUT / "4-embedded.png"))

        # 5. Popup status change.
        open_popup(d, base)
        sel = wait_for(lambda: d.find_elements(By.CSS_SELECTOR, "select.status-select"))
        if sel:
            Select(sel[0]).select_by_value("interview")
            st = wait_for(lambda: rows(user_id)[0]["status"] == "interview")
            check("popup: status change saved", st)
        else:
            check("popup: status change saved", False, "no status select in popup")
        d.save_screenshot(str(OUT / "5-popup-status.png"))

        # 6. Manual "I applied" logic + Google redirect URL (APIs the popup relies on).
        tabs = popup_eval(d, base, "const t = await api.tabs.query({active: true, currentWindow: true}); return t.map(x => x.url);")
        check("tabs.query works from extension page", isinstance(tabs, list) and len(tabs) == 1, str(tabs))
        redirect = popup_eval(d, base, "return api.identity.getRedirectURL();")
        check("identity.getRedirectURL available", isinstance(redirect, str) and redirect.startswith("https://"), redirect)

        # 7. Manual "I applied" on another site (Firefox only: needs a background tab for the popup).
        if BROWSER == "firefox":
            close_popup(d)
            d.get("https://example.com/")
            before = set(d.window_handles)
            with d.context(d.CONTEXT_CHROME):
                # A real toolbar click is what grants activeTab: pin the button and click it.
                d.execute_script(
                    "const w = Services.wm.getMostRecentWindow('navigator:browser');"
                    "const id = 'primora_primora_app-browser-action';"
                    "w.CustomizableUI.addWidgetToArea(id, w.CustomizableUI.AREA_NAVBAR);"
                    "w.document.getElementById(id).querySelector('.unified-extensions-item-action-button').click();")
                time.sleep(2)
                d.execute_script(
                    "Services.wm.getMostRecentWindow('navigator:browser').gBrowser.addTab(arguments[0],"
                    " {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});",
                    f"{base}/popup.html")
            new = wait_for(lambda: list(set(d.window_handles) - before))
            time.sleep(3)  # let the popup mount and read the active tab (example.com)
            d.switch_to.window(new[0])
            btn = wait_for(lambda: d.find_elements(By.XPATH, "//button[normalize-space()='I applied']"))
            company = d.find_element(By.CSS_SELECTOR, "input[placeholder=Company]").get_attribute("value") if btn else None
            check("manual: 'This page' prefilled from the active tab", btn and company, f"company={company!r}")
            d.find_element(By.CSS_SELECTOR, "input[placeholder=Role]").send_keys("Test Role")
            d.save_screenshot(str(OUT / "7-manual.png"))
            btn[0].click()
            got = wait_for(lambda: [r for r in rows(user_id) if r["source"] == "manual"])
            check("manual: 'I applied' saved a row", got and got[0]["url"].startswith("https://example.com"), json.dumps(got)[:200])
            d.close()
            d.switch_to.window(MAIN["handle"])

        # 8. "Open dashboard" opens the in-extension dashboard, signed in with the popup's session.
        open_popup(d, base)
        link = wait_for(lambda: d.find_elements(By.XPATH, "//a[contains(., 'Open dashboard')]"))
        before = set(d.window_handles)
        link[0].click()  # opens dashboard.html in a new tab and closes the popup tab
        if BROWSER == "firefox":
            new = wait_for(lambda: [h for h in d.window_handles if h not in before])
        else:
            # ChromeDriver doesn't hand out tabs an extension creates; find it through CDP, then load it directly.
            d.switch_to.window(MAIN["handle"])
            new = wait_for(lambda: [t for t in d.execute_cdp_cmd("Target.getTargets", {})["targetInfos"]
                                    if t["type"] == "page" and t["url"] == f"{base}/dashboard.html"])
        check("dashboard: link opens a new tab", new)
        if new:
            if BROWSER == "firefox":
                d.switch_to.window(new[0])
            else:
                d.switch_to.new_window("tab")
                d.get(f"{base}/dashboard.html")
            check("dashboard: extension page, not localhost",
                  wait_for(lambda: d.current_url == f"{base}/dashboard.html"), d.current_url)
            body = wait_for(lambda: email in (t := d.find_element(By.TAG_NAME, "body").text) and "Anthropic" in t and t)
            check("dashboard: signed in and lists applications", body, (body or "")[:120].replace("\n", " | "))
            d.save_screenshot(str(OUT / "8-dashboard.png"))
            d.find_element(By.XPATH, "//button[normalize-space()='Sign out']").click()
            check("dashboard: sign-out shows the sign-in form",
                  wait_for(lambda: d.find_elements(By.XPATH, "//button[normalize-space()='Create account']")))
        d.switch_to.window(MAIN["handle"])
    except Exception:
        traceback.print_exc()
        check("no exceptions", False)
    finally:
        if d:
            d.quit()
        requests.delete(f"{URL}/auth/v1/admin/users/{user_id}", headers=ADMIN).raise_for_status()
        print("throwaway user deleted", flush=True)
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
