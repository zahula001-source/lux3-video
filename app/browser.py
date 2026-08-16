"""
V19 - DAI TU THAT SU - Fix tab xoay 100%
- Xoa sach session + Preferences de khong bao gio restore 3 tab
- Chi mo 1 tab Google duy nhat, khong extension, khong proxy, khong gi het
- De test cho chac, sau do moi them IP + extension lai
"""
import os, sys, json, time, threading, subprocess, shutil, random
from pathlib import Path
from typing import Dict
from .fingerprint import get_proxy_dict

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

running_browsers: Dict[str, subprocess.Popen] = {}
running_lock = threading.Lock()

def clean_session_hard(user_data_dir):
    """Xoa TANH BANGH session cu"""
    try:
        default_dir = Path(user_data_dir) / "Default"
        # Xoa het file session
        patterns = ["Current Tabs", "Last Tabs", "Current Session", "Last Session", "Tabs", "Tab Groups", "Sessions", "Session Storage", "Local Storage"]
        if default_dir.exists():
            for item in default_dir.iterdir():
                try:
                    # Xoa bat ky file nao chua Session hoac Tabs
                    if "Session" in item.name or "Tabs" in item.name:
                        if item.is_file():
                            item.unlink()
                        else:
                            shutil.rmtree(item, ignore_errors=True)
                except:
                    pass
            # Xoa thu muc Sessions
            for d in ["Sessions", "Session Storage", "Local Storage"]:
                p = default_dir / d
                if p.exists():
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                    except:
                        pass
        
        # Tao Preferences moi tinh - KHONG restore
        pref_file = default_dir / "Preferences"
        default_dir.mkdir(parents=True, exist_ok=True)
        prefs = {
            "session": {
                "restore_on_startup": 0,
                "startup_urls": ["https://google.com"]
            },
            "startup_pages_migration_time": 0,
            "browser": {
                "has_seen_welcome_page": True
            }
        }
        try:
            pref_file.write_text(json.dumps(prefs), encoding="utf-8")
        except:
            pass
        print(f"Cleaned hard session at {user_data_dir}")
    except Exception as e:
        print(f"Clean hard err {e}")

def get_chromium_runner_simple(profile_id, user_data_dir, proxy_dict, fingerprint, startup_urls=None, startup_mode=None, port=0, enable_ext_btn2=False):
    proxy_str = json.dumps(proxy_dict) if proxy_dict else "None"
    user_data_dir_fs = user_data_dir.replace("\\", "/")
    log_path = str((LOGS_DIR / f"launch_{profile_id}.log").as_posix())
    cookie_file = str((Path(user_data_dir) / "imported_cookies.json").as_posix())
    ext_path_fs = str((DATA_DIR / "extensions" / "fingerprint_spoofer").absolute()).replace("\\", "/")

    screen_str = fingerprint.get("screen", "1920x1080") if fingerprint else "1920x1080"
    try:
        sw, sh = map(int, screen_str.split("x"))
    except:
        sw, sh = 1920, 1080
    random_id = fingerprint.get("random_id", random.randint(100000,999999)) if fingerprint else random.randint(100000,999999)

    lines = []
    lines.append("import sys, time, json, traceback, random")
    lines.append("from pathlib import Path")
    lines.append(f'log_file = Path(r"{log_path}")')
    lines.append(f'cookie_path = Path(r"{cookie_file}")')
    lines.append('log_file.parent.mkdir(parents=True, exist_ok=True)')
    lines.append("def log(m):")
    lines.append("    try:")
    lines.append("        print(str(m), flush=True)")
    lines.append("    except: pass")
    lines.append("    try:")
    lines.append('        with open(log_file, "a", encoding="utf-8", errors="ignore") as f:')
    lines.append('            f.write(str(m) + "\\n")')
    lines.append("    except: pass")
    lines.append("")
    lines.append(f'profile_id = "{profile_id}"')
    lines.append(f'user_data_dir = r"{user_data_dir_fs}"')
    lines.append(f'proxy = {proxy_str}')
    lines.append(f'sw = {sw}')
    lines.append(f'sh = {sh}')
    lines.append(f'random_id = {random_id}')
    
    import json
    lines.append(f'startup_urls_str = {json.dumps(startup_urls if startup_urls else "")}')
    lines.append(f'startup_mode = {json.dumps(startup_mode if startup_mode else "once")}')
    lines.append(f'cdp_port = {port}')
    lines.append(f'enable_ext_btn2 = {"True" if enable_ext_btn2 else "False"}')
    
    lines.append(f'log(f"[{{profile_id}}] V19 SIMPLE - 1 tab Google - ID={{random_id}} CDP={{cdp_port}}")')
    lines.append(f'if proxy:')
    lines.append(f'    log(f"Proxy: {{proxy}}")')
    lines.append("")
    lines.append("try:")
    lines.append("    from playwright.sync_api import sync_playwright")
    lines.append("    with sync_playwright() as p:")
    lines.append("        args = [")
    lines.append('            "--disable-blink-features=AutomationControlled",')
    lines.append('            "--no-first-run",')
    lines.append('            "--no-default-browser-check",')
    lines.append('            "--restore-last-session",')
    lines.append(f'            "--load-extension={ext_path_fs}",')
    lines.append(f'            "--window-size={sw},{sh}",')
    lines.append(f'            "--remote-debugging-port={port}",')
    lines.append("        ]")
    lines.append("        launch_args = dict(")
    lines.append("            user_data_dir=user_data_dir,")
    lines.append("            headless=False,")
    lines.append('            channel="chrome",')
    lines.append('            ignore_default_args=["--disable-extensions"],')
    lines.append("            args=args,")
    lines.append('            downloads_path=str(Path.home() / "Downloads"),')
    lines.append("            accept_downloads=True,")
    lines.append("        )")
    code_no_ext = """
        if proxy:
            launch_args["proxy"] = proxy

        log("Launching...")
        context = p.chromium.launch_persistent_context(**launch_args)
        
        try:
            Path(user_data_dir, "cdp_port.txt").write_text(str(cdp_port))
        except: pass

        log(f"Launched, pages={len(context.pages)}")
        
        def _on_download(download):
            def _save_download():
                try:
                    name = download.suggested_filename
                    if not "." in name:
                        new_name = name + ".mp4"
                        download.save_as(str(Path.home() / "Downloads" / new_name))
                        # Xóa file trắng (không đuôi) được tải về mặc định (có retry vì Windows lock file)
                        try:
                            native_path = Path.home() / "Downloads" / name
                            import time
                            for _ in range(20):
                                if native_path.exists():
                                    try:
                                        native_path.unlink()
                                        break
                                    except:
                                        time.sleep(0.5)
                                else:
                                    break
                        except: pass
                    else:
                        download.save_as(str(Path.home() / "Downloads" / name))
                except Exception as e:
                    log(f"Download err {e}")
            import threading
            threading.Thread(target=_save_download, daemon=True).start()
            
        def _on_page(page):
            page.on("download", _on_download)
            
        context.on("page", _on_page)
        for page in context.pages:
            page.on("download", _on_download)

        try:
            # Playwright tự động nhét 1 tab about:blank vào, mình sẽ xóa nó đi nếu có tab cũ được khôi phục
            if context.pages:
                context.pages[0].wait_for_timeout(1000) # Đợi tab cũ khôi phục
            
            # Xóa tab about:blank
            pages = context.pages
            if len(pages) > 1:
                for pg in pages:
                    if pg.url == "about:blank":
                        try:
                            pg.close()
                        except:
                            pass
            elif len(pages) == 1 and pages[0].url == "about:blank":
                try:
                    pages[0].goto("https://google.com", wait_until="domcontentloaded")
                except:
                    pass
        except:
            pass

        try:
            if startup_urls_str:
                urls = [u.strip() for u in startup_urls_str.splitlines() if u.strip()]
                if startup_mode == 'once':
                    flag_file = Path(user_data_dir) / 'startup_once.flag'
                    if not flag_file.exists():
                        for u in urls:
                            try: context.new_page().goto(u, timeout=10000)
                            except: pass
                        flag_file.touch()
                else: # always
                    existing_urls = [pg.url for pg in context.pages]
                    for u in urls:
                        u_norm = u.replace("https://", "").replace("http://", "").strip("/")
                        if not any(u_norm in eu for eu in existing_urls):
                            try: context.new_page().goto(u, timeout=10000)
                            except: pass
        except Exception as e:
            log(f"Startup urls err {e}")

        # Cookie
        if cookie_path.exists():
            try:
                cookies = json.loads(cookie_path.read_text(encoding="utf-8"))
                for i in range(0, len(cookies), 30):
                    chunk = cookies[i:i+30]
                    try:
                        context.add_cookies(chunk)
                    except:
                        for c in chunk:
                            try:
                                context.add_cookies([c])
                            except:
                                pass
                log(f"Cookies {len(cookies)} OK")
            except Exception as e:
                log(f"Cookie err {e}")

        log("BROWSER_READY - 1 tab Google muot!")

        # Tu dong click Extension Fingerprint Spoofer neu co cai
        try:
            ext_page = context.new_page()
            ext_page.goto("chrome-extension://facgnnelgcipeopfbjcajpaibhhdjgcp/popup.html", wait_until="load", timeout=5000)
            ext_page.wait_for_timeout(1000)
            
            import random
            # Nút 1 (Navigator) luôn bật, nút 2 (Canvas) chỉ bật nếu enable_ext_btn2
            buttons_to_click = ["Spoof Navigator"]
            if enable_ext_btn2:
                if random.random() > 0.5:
                    buttons_to_click.append("Spoof Canvas")
            else:
                # Đảm bảo tắt nút 2 nếu nó đang bật (click để toggle off)
                try:
                    canvas_btn = ext_page.locator("text='Spoof Canvas'")
                    # Nếu nút đang được kích hoạt (màu đỏ) thì click để tắt
                    cls = canvas_btn.get_attribute("class") or ""
                    style = canvas_btn.evaluate("el => el.style.background + el.style.backgroundColor + window.getComputedStyle(el).backgroundColor")
                    if "red" in str(style).lower() or "rgb(239" in str(style) or "active" in cls.lower():
                        canvas_btn.click(timeout=1000)
                except: pass
            for btn in buttons_to_click:
                try:
                    ext_page.locator(f"text='{btn}'").click(timeout=1000)
                    ext_page.wait_for_timeout(300)
                except:
                    pass
            
            ext_page.close()
            log("Extension Fingerprint Spoofer auto-configured!")
        except Exception:
            try:
                ext_page.close()
            except:
                pass

        try:
            while context.pages:
                context.pages[0].wait_for_timeout(1000)
        except:
            pass
except Exception as e:
    log(f"FATAL {e}")
    log(traceback.format_exc())
    sys.exit(1)
"""
    lines.append(code_no_ext)
    return "\n".join(lines)

def get_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def launch_profile(profile, req=None):
    with running_lock:
        if profile.id in running_browsers:
            proc = running_browsers[profile.id]
            if proc.poll() is None:
                return {"status": "already_running", "pid": proc.pid}
            else:
                del running_browsers[profile.id]

    proxy_dict = get_proxy_dict(profile.proxy) if profile.proxy else None
    user_data_dir = profile.user_data_dir
    os.makedirs(user_data_dir, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    log_file = LOGS_DIR / f"launch_{profile.id}.log"
    if log_file.exists():
        try:
            log_file.unlink()
        except:
            pass

    fp_path = Path(user_data_dir) / "fingerprint.json"
    if not fp_path.exists():
        try:
            fp_path.write_text(json.dumps(profile.fingerprint, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        except:
            pass

    startup_urls = req.startup_urls if req else None
    startup_mode = req.startup_mode if req else None
    enable_ext_btn2 = req.enable_ext_btn2 if req else False
    port = get_free_port()
    py_code = get_chromium_runner_simple(profile.id, user_data_dir, proxy_dict, profile.fingerprint, startup_urls, startup_mode, port, enable_ext_btn2)

    tmp_script = DATA_DIR / f"runner_{profile.id}.py"
    tmp_script.write_text(py_code, encoding="utf-8")

    cmd = [sys.executable, str(tmp_script)]
    try:
        log_file_handle = open(log_file, "w", encoding="utf-8", errors="ignore")
        proc = subprocess.Popen(cmd, stdout=log_file_handle, stderr=subprocess.STDOUT)
        for _ in range(30):
            time.sleep(0.5)
            if proc.poll() is not None:
                try:
                    log_file_handle.close()
                except:
                    pass
                txt = log_file.read_text(encoding="utf-8", errors="ignore")[-5000:] if log_file.exists() else "No log"
                return {"status": "error", "message": f"Exit {proc.returncode}\n{txt}"}
            if log_file.exists():
                try:
                    if "BROWSER_READY" in log_file.read_text(encoding="utf-8", errors="ignore"):
                        break
                except:
                    pass
        with running_lock:
            running_browsers[profile.id] = proc
        return {"status": "launched", "pid": proc.pid}
    except Exception as e:
        import traceback
        return {"status": "error", "message": f"{e}\n{traceback.format_exc()}"}

def launch_profile_with_fallback(profile, req=None):
    return launch_profile(profile, req)

def close_profile(profile_id: str):
    with running_lock:
        proc = running_browsers.get(profile_id)
        if not proc:
            return {"status": "not_running"}
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            del running_browsers[profile_id]
            return {"status": "closed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def is_running(profile_id: str) -> bool:
    with running_lock:
        proc = running_browsers.get(profile_id)
        if not proc:
            return False
        return proc.poll() is None

def list_running():
    with running_lock:
        return {pid: proc.pid for pid, proc in running_browsers.items() if proc.poll() is None}
