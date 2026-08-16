"""
Antidetect Unlimited V4 - Hỗ trợ Cookie BitBrowser + Random Fingerprint + Tabs persistence
"""
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

from app.models import ProfileCreate, LaunchRequest
from app.manager import manager
from app.browser import launch_profile_with_fallback, close_profile, is_running, list_running

video_tasks: dict = {}  # task_id -> status/result / "static"

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
app = FastAPI(title="Antidetect Unlimited - Camoufox Edition V4", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
@app.get("/api/profiles")
def get_profiles():
    profiles = manager.list_profiles()
    result = []
    for p in profiles:
        d = p.model_dump()
        d["running"] = is_running(p.id)
        # Đếm cookie imported
        cookie_file = Path(p.user_data_dir) / "imported_cookies.json"
        d["cookies_count"] = 0
        if cookie_file.exists():
            try:
                import json
                d["cookies_count"] = len(json.loads(cookie_file.read_text(encoding="utf-8")))
            except:
                pass
        # Tabs
        tabs_file = Path(p.user_data_dir) / "tabs.json"
        d["tabs_count"] = 0
        if tabs_file.exists():
            try:
                import json
                d["tabs_count"] = len(json.loads(tabs_file.read_text(encoding="utf-8")))
            except:
                pass
        result.append(d)
    return result

@app.post("/api/profiles")
def create_profile(data: ProfileCreate):
    name = data.name
    if not name or name.strip() == "":
        profiles = manager.list_profiles()
        max_id = len(profiles)
        import re
        for p in profiles:
            m = re.search(r'tk\s*(\d+)', p.name.lower())
            if m:
                num = int(m.group(1))
                if num > max_id:
                    max_id = num
        name = f"tk {max_id + 1}"
        
    profile = manager.create_profile(
        name=name,
        os=data.os,
        browser=data.browser,
        proxy=data.proxy,
        notes=data.notes,
        fingerprint_preset=data.fingerprint_preset
    )
    return profile.model_dump()

@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: str):
    if is_running(profile_id):
        close_profile(profile_id)
    ok = manager.delete_profile(profile_id)
    if not ok:
        raise HTTPException(404, "Profile not found")
    return {"ok": True}

@app.post("/api/profiles/{profile_id}/duplicate")
def duplicate_profile(profile_id: str):
    new_p = manager.duplicate_profile(profile_id)
    if not new_p:
        raise HTTPException(404, "Profile not found")
    return new_p.model_dump()

@app.post("/api/profiles/{profile_id}/launch")
def launch_profile_endpoint(profile_id: str, req: LaunchRequest = None):
    profile = manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
        
    for task in video_tasks.values():
        if task.get("status") in ["running", "pending"]:
            if task.get("params", {}).get("profile_id") == profile_id:
                raise HTTPException(400, f"Profile '{profile.name}' đang chạy ngầm để tạo Video. Vui lòng đợi tạo xong!")
                
    do_random = False
    if req and req.auto_random_fp:
        do_random = True
    elif getattr(profile, 'auto_random_fp', False):
        do_random = True
        
    if do_random:
        profile = manager.randomize_fingerprint(profile_id)

    result = launch_profile_with_fallback(profile, req)
    if result["status"] == "launched":
        manager.update_last_used(profile_id)
        return {"ok": True, "pid": result["pid"], "browser": profile.browser}
    elif result["status"] == "already_running":
        return {"ok": True, "message": "Already running", "pid": result["pid"]}
    else:
        raise HTTPException(500, result.get("message", "Launch failed"))

@app.post("/api/profiles/{profile_id}/auto-random-fp")
def toggle_auto_random_fp_endpoint(profile_id: str, payload: dict = Body(...)):
    state = payload.get("state", False)
    if manager.toggle_auto_random_fp(profile_id, state):
        return {"ok": True, "auto_random_fp": state}
    raise HTTPException(404, "Profile not found")

@app.post("/api/profiles/{profile_id}/close")
def close_profile_endpoint(profile_id: str):
    result = close_profile(profile_id)
    return result

@app.post("/api/profiles/{profile_id}/random-fingerprint")
def random_fingerprint(profile_id: str):
    """Nút Random Fingerprint như BitBrowser - đổi ngay lập tức mà vẫn giữ cookie"""
    profile = manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    
    was_running = is_running(profile_id)
    if was_running:
        close_profile(profile_id)
        import time
        time.sleep(1.5)
    
    new_p = manager.randomize_fingerprint(profile_id)
    
    # Nếu đang chạy thì mở lại luôn với fingerprint mới (giữ nguyên cookies)
    if was_running:
        result = launch_profile_with_fallback(new_p)
        if result["status"] == "launched":
            return {"ok": True, "message": f"Đã random fingerprint mới ({new_p.os}) và mở lại, cookies vẫn giữ!", "profile": new_p.model_dump(), "pid": result["pid"]}
        else:
            return {"ok": True, "message": f"Đã random fingerprint mới ({new_p.os}) nhưng lỗi mở lại: {result.get('message')}", "profile": new_p.model_dump()}
    
    return {"ok": True, "message": f"Đã random fingerprint mới: {new_p.os} - {new_p.fingerprint.get('random_id')}", "profile": new_p.model_dump()}

@app.post("/api/profiles/{profile_id}/import-cookies")
def import_cookies(profile_id: str, payload: dict = Body(...)):
    """Import cookies từ BitBrowser - dán JSON vào"""
    profile = manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    
    cookies_raw = payload.get("cookies") or payload.get("cookie")
    if not cookies_raw:
        raise HTTPException(400, "Thiếu trường 'cookies' - dán JSON array từ BitBrowser")
    
    result = manager.import_cookies(profile_id, cookies_raw)
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    # Nếu đang chạy thì báo cần restart
    if is_running(profile_id):
        result["need_restart"] = True
        result["message"] = f"Đã import {result['imported']}/{result['total']} cookies! Đóng và mở lại profile để cookie có hiệu lực (tabs vẫn giữ)."
    else:
        result["message"] = f"Đã import {result['imported']}/{result['total']} cookies! Mở profile lên là dùng được."
    
    return result

@app.get("/api/profiles/{profile_id}/export-cookies")
def export_cookies_endpoint(profile_id: str):
    profile = manager.get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    
    if is_running(profile_id):
        raise HTTPException(400, "Vui lòng ĐÓNG profile trước khi xuất cookie (Playwright đang lock thư mục)!")
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Mo headless browser de doc cookie
            context = p.chromium.launch_persistent_context(
                profile.user_data_dir, 
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            cookies = context.cookies()
            context.close()
            return {"ok": True, "cookies": cookies}
    except Exception as e:
        raise HTTPException(500, f"Lỗi đọc cookies: {e}")

@app.get("/api/profiles/{profile_id}/logs")
def get_logs(profile_id: str):
    log_file = BASE_DIR / "data" / "logs" / f"launch_{profile_id}.log"
    if not log_file.exists():
        return {"log": "Chưa có log"}
    return {"log": log_file.read_text(encoding="utf-8", errors="ignore")[-5000:]}

@app.get("/api/running")
def get_running():
    return list_running()

@app.get("/api/health")
def health():
    return {"status": "ok", "profiles": len(manager.list_profiles()), "running": len(list_running())}

@app.get("/api/profiles/free")
def get_free_profile():
    used_profiles = set()
    for task in video_tasks.values():
        if task.get("status") in ["running", "pending"]:
            used_profiles.add(task.get("params", {}).get("profile_id"))
    for p in list_running():
        used_profiles.add(p["id"])
    
    all_profiles = manager.list_profiles()
    free_profiles = [p.id for p in all_profiles if p.id not in used_profiles]
    return {"free_profiles": free_profiles}

@app.get("/api/select-folder")
def select_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder_path = filedialog.askdirectory(title="Chọn thư mục lưu Video")
        root.destroy()
        return {"path": folder_path or ""}
    except Exception as e:
        return {"path": ""}

@app.post("/api/profiles/{profile_id}/auto-signup")
def auto_signup_endpoint(profile_id: str):
    import threading
    from pathlib import Path
    
    profile = manager.get_profile(profile_id)
    if not profile: raise HTTPException(404, "Profile not found")
    
    port_file = Path(profile.user_data_dir) / "cdp_port.txt"
    if not port_file.exists():
        raise HTTPException(400, "Profile đang không chạy hoặc không có CDP port. Hãy mở lại Chrome!")
        
    try:
        port = int(port_file.read_text().strip())
    except:
        raise HTTPException(400, "Invalid CDP port.")

    def run_auto_signup():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
                context = browser.contexts[0]
                
                # 0. Cài extension Fingerprint Spoofer trước tiên
                ext_url = "https://chromewebstore.google.com/detail/fingerprint-spoofer/facgnnelgcipeopfbjcajpaibhhdjgcp?hl=vi-"
                ext_page = None
                for page in context.pages:
                    if "fingerprint-spoofer" in page.url:
                        ext_page = page
                        break
                if not ext_page:
                    ext_page = context.new_page()
                    ext_page.goto(ext_url, timeout=30000)
                
                ext_page.bring_to_front()
                ext_page.wait_for_timeout(3000)
                
                # Kiểm tra xem đã cài chưa (nút sẽ đổi thành "Đã cài đặt" / "Remove from Chrome")
                already_installed = False
                try:
                    already_installed = ext_page.locator("text=Đã cài đặt").is_visible(timeout=1000) or \
                                       ext_page.locator("text=Remove from Chrome").is_visible(timeout=1000)
                except: pass
                
                if not already_installed:
                    # Click "Thêm vào Chrome" / "Add to Chrome"
                    try:
                        ext_page.locator("text=Thêm vào Chrome").click(timeout=5000)
                    except:
                        try:
                            ext_page.locator("text=Add to Chrome").click(timeout=5000)
                        except:
                            ext_page.evaluate("""() => {
                                let all = document.querySelectorAll('button, span, a');
                                for(let el of all){
                                    let t = el.innerText.trim();
                                    if(t === 'Thêm vào Chrome' || t === 'Add to Chrome') { el.click(); return; }
                                }
                            }""")
                    
                    # Đợi dialog "Add extension" xuất hiện (khoảng 2-4 giây Chrome mới bật lên)
                    ext_page.wait_for_timeout(4000)
                    
                    # Dialog native Chrome -> ấn Enter để confirm "Add extension"
                    ext_page.keyboard.press("Enter")
                    
                    # Đợi cài xong (nút đổi thành "Đã cài đặt" hoặc xuất hiện popup notification)
                    ext_page.wait_for_timeout(4000)
                
                # Đóng tab extension sau khi cài xong
                try:
                    ext_page.close()
                except: pass
                
                # 1. Tinyhost
                tinyhost_page = None
                for page in context.pages:
                    if "tinyhost.shop" in page.url:
                        tinyhost_page = page
                        break
                if not tinyhost_page:
                    tinyhost_page = context.new_page()
                    tinyhost_page.goto("https://tinyhost.shop/", timeout=30000)
                
                tinyhost_page.bring_to_front()
                tinyhost_page.wait_for_timeout(3000)
                
                email = tinyhost_page.evaluate(r"""() => {
                    let m = document.body.innerText.match(/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/i);
                    return m ? m[1] : "";
                }""")
                if not email:
                    print("Could not extract email from tinyhost!")
                    browser.disconnect()
                    return
                
                pwd = email.split('@')[0] + '@H1'
                
                # 2. BFL Sign up
                bfl_page = None
                for page in context.pages:
                    if "auth.bfl.ai" in page.url or "dashboard.bfl.ai" in page.url:
                        bfl_page = page
                        break
                if not bfl_page:
                    bfl_page = context.new_page()
                
                bfl_page.bring_to_front()
                bfl_page.goto("https://auth.bfl.ai/register?redirect_uri=https%3A%2F%2Fdashboard.bfl.ai%2F", timeout=30000)
                
                try:
                    bfl_page.locator("text=Sign up").first.click(timeout=5000)
                except: pass
                
                bfl_page.wait_for_selector('input[type="email"]')
                bfl_page.locator('input[type="email"]').fill(email)
                
                pwds = bfl_page.locator('input[type="password"]')
                pwds.nth(0).fill(pwd)
                if pwds.count() > 1:
                    pwds.nth(1).fill(pwd)
                
                try:
                    bfl_page.locator("button:has-text('Sign up')").last.click(timeout=3000)
                except:
                    bfl_page.evaluate("""() => {
                        let btns = document.querySelectorAll('button');
                        for(let b of btns) {
                            if(b.innerText.includes('Sign up')) { b.click(); }
                        }
                    }""")
                
                try:
                    bfl_page.wait_for_selector("text=Check your email", timeout=30000)
                except: pass
                
                # 3. Tinyhost confirm
                tinyhost_page.bring_to_front()
                view_clicked = False
                for _ in range(30):
                    try:
                        view_btn = tinyhost_page.locator("text=View")
                        if view_btn.count() > 0:
                            view_btn.first.click()
                            view_clicked = True
                            break
                    except: pass
                    
                    try:
                        tinyhost_page.locator("text=Check Inbox").click(timeout=1000)
                    except: pass
                    tinyhost_page.wait_for_timeout(2000)
                
                if not view_clicked:
                    print("No email received.")
                    browser.disconnect()
                    return
                
                with context.expect_page() as new_page_info:
                    tinyhost_page.locator("text=Confirm my email").click()
                confirm_page = new_page_info.value
                
                confirm_page.wait_for_load_state()
                
                try:
                    confirm_page.wait_for_selector('input[type="email"]', timeout=10000)
                    confirm_page.locator('input[type="email"]').fill(email)
                    confirm_page.locator('input[type="password"]').fill(pwd)
                    try:
                        confirm_page.locator("button:has-text('Sign in')").click(timeout=3000)
                    except:
                        confirm_page.evaluate("""() => {
                            let btns = document.querySelectorAll('button');
                            for(let b of btns) {
                                if(b.innerText.includes('Sign in')) { b.click(); }
                            }
                        }""")
                    
                    confirm_page.wait_for_selector("text=Default", timeout=20000)
                    print("Auto signup SUCCESS! Proceeding to setup dashboard...")
                    
                    # Click Playground
                    try:
                        confirm_page.locator("a[href$='/playground']").first.click(timeout=5000)
                        confirm_page.wait_for_timeout(2000)
                    except: pass
                    
                    # Click All parameters
                    try:
                        confirm_page.locator("button", has_text="All parameters").first.click(timeout=5000)
                        confirm_page.wait_for_timeout(1000)
                    except: pass
                    
                    # Set Aspect ratio to 9:16
                    try:
                        # Bấm nút Aspect ratio bên ngoài để mở panel
                        confirm_page.locator("button:has-text('Aspect ratio')").click(timeout=3000)
                        confirm_page.wait_for_timeout(500)
                        # Bấm vào combobox chọn auto
                        confirm_page.locator("button[role='combobox']").first.click(timeout=3000)
                        confirm_page.wait_for_timeout(500)
                        # Chọn 9:16
                        confirm_page.locator("text=9:16").click(timeout=3000)
                    except: pass
                    
                    # Set Duration to 20
                    try:
                        # Bấm nút Duration bên ngoài để mở panel
                        confirm_page.locator("button:has-text('Duration')").click(timeout=3000)
                        confirm_page.wait_for_timeout(500)
                        confirm_page.locator('input[type="number"]').fill("20")
                        confirm_page.locator('input[type="number"]').press("Enter")
                    except: pass
                    
                    print("Dashboard setup complete!")
                    
                except Exception as e:
                    print(f"Login confirm/setup err: {e}")
                
                # Close tinyhost
                try:
                    tinyhost_page.close()
                except: pass
                
                # Focus dashboard
                confirm_page.bring_to_front()
                
                browser.disconnect()
        except Exception as e:
            print(f"Auto signup FATAL err: {e}")

    threading.Thread(target=run_auto_signup, daemon=True).start()
    return {"ok": True, "message": "Bắt đầu Auto Đăng ký..."}

# ===== VIDEO CREATION API =====
import threading
import uuid as uuid_module
from fastapi import UploadFile, File, Form
from fastapi.responses import JSONResponse

def _open_browser_with_fp(p, profile, ext_path, attempt=1, enable_ext_btn2=False, is_headless=False):
    """Mở trình duyệt với Random FP và kích hoạt extension
    only_navigator=True: chỉ bật nút 1 (Spoof Navigator) - dùng khi cần tải ảnh
    close_old_tabs=True: đóng hết các tab cũ khi mở lên (chỉ dùng cho video creation)
    """
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--restore-last-session",
        f"--load-extension={ext_path}",
    ]
    if is_headless:
        args.append("--headless=new")
        
    context = p.chromium.launch_persistent_context(
        profile.user_data_dir,
        headless=False,
        channel="chrome",
        ignore_default_args=["--disable-extensions"],
        args=args,
        downloads_path=str(Path.home() / "Downloads"),
        accept_downloads=True
    )
    
    # Bắt sự kiện tải file thủ công trên trình duyệt để thêm đuôi .mp4 nếu thiếu
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
            except:
                pass
        import threading
        threading.Thread(target=_save_download, daemon=True).start()
            
    def _on_page(page):
        page.on("download", _on_download)
        
    context.on("page", _on_page)
    for page in context.pages:
        page.on("download", _on_download)
    
    # Kích hoạt extension Fingerprint Spoofer
    try:
        import random
        ext_page = context.new_page()
        ext_page.goto("chrome-extension://facgnnelgcipeopfbjcajpaibhhdjgcp/popup.html", wait_until="load", timeout=5000)
        try:
            ext_page.wait_for_function("document.querySelector('#spoofCanvas') && document.querySelector('#spoofCanvas').textContent !== ''", timeout=3000)
        except:
            pass
            
        # Lần 1 (attempt=1) -> Tắt hết
        # Lần 2 (attempt=2) -> Bật (Nút 1 ON, Nút 2 tuỳ enable_ext_btn2)
        # Lần 3 (attempt=3) -> Tắt hết
        # Lần 4 (attempt=4) -> Bật...
        turn_on = (attempt > 1 and attempt % 2 == 0)
        
        script = f"""() => {{
            const navBtn = document.querySelector('#spoofNav');
            const canBtn = document.querySelector('#spoofCanvas');
            
            if ({'true' if turn_on else 'false'}) {{
                // Bật
                if (navBtn && !navBtn.classList.contains('btn-danger')) navBtn.click();
                if ({'true' if enable_ext_btn2 else 'false'}) {{
                    if (canBtn && !canBtn.classList.contains('btn-danger')) canBtn.click();
                }} else {{
                    if (canBtn && canBtn.classList.contains('btn-danger')) canBtn.click();
                }}
            }} else {{
                // Tắt hết
                if (navBtn && navBtn.classList.contains('btn-danger')) navBtn.click();
                if (canBtn && canBtn.classList.contains('btn-danger')) canBtn.click();
            }}
        }}"""
        
        try:
            ext_page.evaluate(script)
        except: pass
                
        ext_page.close()
    except:
        pass
    
    # Đóng tab trống của extension hoặc about:blank
    try:
        for pg in context.pages:
            try:
                if pg.url in ('about:blank', '') or pg.url.startswith('chrome-extension://'):
                    pg.close()
            except:
                pass
    except:
        pass
    return context

def _activate_canvas_spoof(context, ext_path):
    """Kích hoạt Spoof Canvas SAU khi đã upload ảnh thành công"""
    try:
        ext_page = context.new_page()
        ext_page.goto("chrome-extension://facgnnelgcipeopfbjcajpaibhhdjgcp/popup.html", wait_until="load", timeout=5000)
        ext_page.wait_for_timeout(500)
        try:
            ext_page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('*'));
                const canOff = btns.find(e => e.innerText === 'Spoof Canvas');
                if (canOff) canOff.click();
            }""")
        except:
            pass
        ext_page.close()
    except:
        pass


def _fill_form(page, context, ext_path, prompt, img1_path, img2_path, video_tasks, task_id, is_retry=False):
    """Điền prompt + upload ảnh vào bfl.ai. Trả về True nếu OK."""
    # Đợi textarea
    try:
        page.wait_for_selector("textarea[placeholder*='Describe']", timeout=15000)
    except:
        return False

    # Điền prompt bằng JS (tránh overlay chặn)
    page.evaluate("""(text) => {
        const ta = document.querySelector("textarea[placeholder*='Describe']");
        if (ta) {
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            nativeSetter.call(ta, text);
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }""", prompt)
    page.wait_for_timeout(800)

    if is_retry:
        # Nếu là retry, ảnh đã được lưu ở session bfl.ai nên KHÔNG CẦN TẢI LẠI
        video_tasks[task_id] = {"status": "running", "message": "Form đã sẵn sàng (bỏ qua bước tải ảnh)."}
        return True

    # Bỏ ảnh cũ trước khi tải ảnh mới (kể cả khi không có ảnh mới cũng bỏ)
    try:
        page.evaluate("""() => {
            const removeBtns = document.querySelectorAll("button[aria-label^='Remove']");
            removeBtns.forEach(b => b.click());
        }""")
        page.wait_for_timeout(1000)
    except:
        pass

    # Click nút "All parameters" để hiện phần tải ảnh (giao diện bfl.ai mới cập nhật)
    try:
        page.evaluate("""() => {
            const btns = document.querySelectorAll("button");
            for (let b of btns) {
                if (b.innerText && b.innerText.toUpperCase().includes('ALL PARAMETERS')) {
                    b.click();
                    break;
                }
            }
        }""")
        page.wait_for_timeout(1000)
    except:
        pass

    img1_ok = False
    if img1_path and Path(img1_path).exists():
        # Upload ảnh 1 - Start frame (Spoof Canvas CHƯA được bật ở bước này)
        video_tasks[task_id] = {"status": "running", "message": "Đang tải ảnh 1 (Start frame)..."}
        try:
            with page.expect_file_chooser(timeout=5000) as fc_info:
                page.locator("button[aria-label='Attach start frame']").click()
            fc_info.value.set_files(img1_path)
            page.wait_for_timeout(2000)
            img1_ok = True
        except:
            try:
                page.locator("input[type='file']").first.set_input_files(img1_path)
                page.wait_for_timeout(2000)
                img1_ok = True
            except Exception as e:
                video_tasks[task_id] = {"status": "running", "message": f"Cảnh báo tải ảnh 1: {e}"}

    # ✅ Ảnh 1 đã upload thành công → Giờ mới bật Spoof Canvas an toàn
    if img1_ok:
        video_tasks[task_id] = {"status": "running", "message": "Ảnh 1 OK! Đang kích hoạt Spoof Canvas..."}
        _activate_canvas_spoof(context, ext_path)
        page.wait_for_timeout(500)

    # Upload ảnh 2 - End frame (optional)
    if img2_path and Path(img2_path).exists():
        video_tasks[task_id] = {"status": "running", "message": "Đang tải ảnh 2 (End frame)..."}
        try:
            with page.expect_file_chooser(timeout=5000) as fc_info:
                page.locator("button[aria-label='Attach end frame']").click()
            fc_info.value.set_files(img2_path)
            page.wait_for_timeout(2000)
        except:
            try:
                page.locator("input[type='file']").nth(1).set_input_files(img2_path)
                page.wait_for_timeout(2000)
            except:
                pass
    return True

def _get_generating_status(page, target_prompt=None) -> str:
    """Kiểm tra xem có xuất hiện 'GENERATING' hoặc 'QUEUED' ở giữa màn hình không và lấy text"""
    try:
        snippet = ""
        if target_prompt:
            snippet = " ".join(target_prompt.split())[:30].strip()
            
        result = page.evaluate("""(snippet) => {
            function findStatusText(container) {
                const allElements = Array.from(container.querySelectorAll('*'));
                for (let el of allElements) {
                    if (el.children.length === 0) {
                        const txt = (el.innerText || "").toUpperCase().trim();
                        if (txt.startsWith('QUEUED') || txt.startsWith('GENERATING')) {
                            if (txt.includes('VOLUME')) continue;
                            const parent = el.parentElement;
                            if (parent) {
                                const pText = parent.innerText.replace(/\\n/g, ' ');
                                if (pText.length < 50 && pText.match(/\\d/)) {
                                    return pText;
                                }
                            }
                        }
                    }
                }
                return null;
            }
            
            if (snippet) {
                const articles = document.querySelectorAll('article');
                for (let a of articles) {
                    if (a.textContent.includes(snippet)) {
                        return findStatusText(a);
                    }
                }
                return null;
            } else {
                return findStatusText(document);
            }
        }""", snippet)
        return result
    except:
        return None

def _is_rate_limited(page) -> bool:
    """Kiểm tra xem có bị lỗi hệ thống (Rate limited, 503, Over capacity) không"""
    try:
        result = page.evaluate("""() => {
            const allText = (document.body.innerText || "").toUpperCase();
            return allText.includes('RATE LIMITED') || 
                   allText.includes('SYSTEM_ERROR') ||
                   allText.includes('SERVICE ISSUE') ||
                   allText.includes('STATUS 503') ||
                   allText.includes('OVER CAPACITY');
        }""")
        return result
    except:
        return False

def _get_new_video_url(page, target_prompt: str):
    """Lấy URL video MỚI nhất có chứa prompt tương ứng. Đảm bảo 100% không bắt nhầm video cũ."""
    try:
        snippet = " ".join(target_prompt.split())[:30].strip()
        result = page.evaluate("""(snippet) => {
            const articles = document.querySelectorAll('article');
            for (let a of articles) {
                if (a.textContent.includes(snippet)) {
                    const videos = a.querySelectorAll('video');
                    for (let v of videos) {
                        if (v.src && v.src.startsWith('http')) return v.src;
                        const s = v.querySelector('source');
                        if (s && s.src && s.src.startsWith('http')) return s.src;
                    }
                }
            }
            return null;
        }""", snippet)
        
        if result:
            return result
    except:
        pass
    return None

def run_video_automation(task_id, prompt, img1_path, img2_path, profile_id, save_path, is_headless=False, enable_ext_btn2=False):
    """Background thread: opens bfl.ai và tạo video với logic retry thông minh"""
    from playwright.sync_api import sync_playwright
    import random
    import urllib.request
    import urllib.parse
    import uuid
    from pathlib import Path

    if not save_path:
        save_path = str(Path.home() / "Downloads")
    else:
        save_path = str(Path(save_path))

    profile = manager.get_profile(profile_id)
    if not profile:
        video_tasks[task_id] = {"status": "error", "message": "Profile not found"}
        return

    ext_path = str((Path(BASE_DIR) / "data" / "extensions" / "fingerprint_spoofer").absolute())
    MAX_RETRIES = 20

    video_tasks[task_id] = {"status": "running", "message": "Đang mở trình duyệt..."}

    try:
        with sync_playwright() as p:
            # Lần 1 -> Tắt hết (attempt=1)
            context = _open_browser_with_fp(p, profile, ext_path, attempt=1, enable_ext_btn2=enable_ext_btn2, is_headless=is_headless)
            page = context.new_page()
            
            # Dọn dẹp ĐÓNG HẾT các tab cũ (nếu có) để gọn gàng, chỉ giữ lại tab page vừa tạo
            try:
                for pg in context.pages:
                    if pg != page:
                        try: pg.close()
                        except: pass
            except: pass

            # Ghi nhớ các video URL cũ đang có sẵn (để không bắt nhầm video cũ)
            video_tasks[task_id] = {"status": "running", "message": "Đang truy cập bfl.ai..."}
            page.goto("https://dashboard.bfl.ai/playground?model=flux-3", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Ghi nhớ video cũ đang hiển thị trước khi Generate
            known_video_urls = set()
            try:
                existing = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('video')).map(v => v.src || '').filter(s => s.startsWith('http'));
                }""")
                known_video_urls = set(existing or [])
            except:
                known_video_urls = set()

            old_video_urls = []
            
            def _clear_old_videos():
                nonlocal known_video_urls
                page.wait_for_timeout(2000)
                initial_status = _get_generating_status(page)
                if initial_status:
                    video_tasks[task_id] = {"status": "running", "message": f"Phát hiện tiến trình cũ: {initial_status}. Đang chờ hoàn thành trước..."}
                    for i in range(600):
                        page.wait_for_timeout(1000)
                        st = _get_generating_status(page)
                        if st:
                            video_tasks[task_id]["message"] = f"Đang chờ tiến trình cũ: {st}"
                        else:
                            break
                    
                    video_tasks[task_id]["message"] = "Đang dọn dẹp video cũ..."
                    # Đợi tối đa 20s để thẻ <video> của video cũ xuất hiện
                    for _ in range(20):
                        page.wait_for_timeout(1000)
                        try:
                            new_existing = page.evaluate("""() => {
                                return Array.from(document.querySelectorAll('video')).map(v => v.src || '').filter(s => s.startsWith('http'));
                            }""")
                            current_videos = set(new_existing or [])
                            new_vids = current_videos - known_video_urls
                            if new_vids:
                                import uuid
                                import urllib.parse
                                out_dir = Path(save_path)
                                out_dir.mkdir(parents=True, exist_ok=True)
                                for nv in new_vids:
                                    uid = str(uuid.uuid4())[:8]
                                    out_file = out_dir / f"old_{task_id}_{uid}.mp4"
                                    try:
                                        resp = context.request.get(nv)
                                        if resp.ok:
                                            with open(out_file, "wb") as f:
                                                f.write(resp.body())
                                            old_video_urls.append(f"/api/video/download/old_{task_id}_{uid}?path={urllib.parse.quote(str(out_file))}")
                                    except Exception as e:
                                        pass
                                known_video_urls.update(current_videos)
                                break
                        except: pass

            # Gọi dọn dẹp ở lần đầu
            _clear_old_videos()

            # Điền form lần đầu
            video_tasks[task_id] = {"status": "running", "message": "Đang điền thông tin..."}
            if not _fill_form(page, context, ext_path, prompt, img1_path, img2_path, video_tasks, task_id):
                video_tasks[task_id] = {"status": "error", "message": "Không load được trang bfl.ai. Hãy đăng nhập trước!"}
                context.close()
                return

            video_url = None
            for attempt in range(1, MAX_RETRIES + 1):
                video_tasks[task_id] = {"status": "running", "message": f"Lần thử {attempt}/{MAX_RETRIES}: Đang nhấn Generate..."}

                # Click Generate
                try:
                    gen_btn = page.locator("button[aria-label='Generate']")
                    gen_btn.wait_for(state="visible", timeout=5000)
                    gen_btn.click()
                except:
                    page.evaluate("""() => {
                        const btn = document.querySelector("button[aria-label='Generate']");
                        if (btn) btn.click();
                    }""")

                # Chờ tối đa 30s để thấy "GENERATING... • time"
                video_tasks[task_id] = {"status": "running", "message": f"Lần thử {attempt}/{MAX_RETRIES}: Chờ GENERATING... (tối đa 30s)..."}
                found_generating = False
                rate_limited = False
                
                for tick in range(30):
                    page.wait_for_timeout(1000)
                    status_text = _get_generating_status(page, prompt)
                    if status_text:
                        found_generating = True
                        video_tasks[task_id]["message"] = f"Trạng thái: {status_text}"
                        break
                    
                    if _is_rate_limited(page):
                        rate_limited = True
                        video_tasks[task_id] = {"status": "running", "message": f"Lần thử {attempt}/{MAX_RETRIES}: Server BFL báo quá tải! Đóng và thử lại ngay..."}
                        break
                    video_tasks[task_id]["message"] = f"Lần thử {attempt}/{MAX_RETRIES}: Chờ GENERATING... {tick+1}s/30s"

                # NẾU THẤY QUEUED/GENERATING THÌ VÀO VÒNG LẶP CHỜ 10 PHÚT
                if found_generating:
                    video_tasks[task_id] = {"status": "running", "message": "✅ GENERATING... đã xác nhận! Đang đợi video hoàn thành..."}
                    for i in range(600):  # đợi tối đa 10 phút
                        page.wait_for_timeout(1000)

                        status_text = _get_generating_status(page, prompt)
                        still_generating = bool(status_text)
                        
                        if still_generating:
                            video_tasks[task_id]["message"] = f"Trạng thái trên web: {status_text}"
                        else:
                            video_tasks[task_id]["message"] = f"Đang chờ video hiển thị... {i//60:02d}:{i%60:02d}"

                        if _is_rate_limited(page):
                            rate_limited = True
                            video_tasks[task_id] = {"status": "running", "message": f"Lần thử {attempt}/{MAX_RETRIES}: Rate limited giữa chừng! Đóng và thử lại..."}
                            break

                        # Đồng thời tìm video mới (lọc chính xác theo prompt)
                        new_url = _get_new_video_url(page, prompt)
                        if new_url:
                            video_url = new_url
                            break

                        if not still_generating and i > 5:
                            page.wait_for_timeout(2000)
                            new_url = _get_new_video_url(page, prompt)
                            if new_url:
                                video_url = new_url
                            break
                            
                # NẾU TÌM THẤY VIDEO URL THÌ XONG!
                if video_url:
                    break
                    
                # NẾU CHƯA XONG MÀ HẾT 10 LẦN THỬ THÌ BÁO LỖI
                if attempt >= MAX_RETRIES:
                    video_tasks[task_id] = {"status": "error", "message": f"Đã thử {MAX_RETRIES} lần nhưng không tạo được video hoặc server quá tải liên tục."}
                    try: context.close()
                    except: pass
                    return

                # Nếu bị rate limited hoặc không thấy generating -> Đóng Chrome, đổi FP, mở lại
                if not rate_limited and not found_generating:
                    video_tasks[task_id] = {"status": "running", "message": f"Lần thử {attempt}/{MAX_RETRIES}: Không thấy GENERATING, đang đóng và mở lại Chrome..."}
                
                try: context.close()
                except: pass

                manager.randomize_fingerprint(profile_id)
                profile = manager.get_profile(profile_id)

                import time
                time.sleep(2)
                context = _open_browser_with_fp(p, profile, ext_path, attempt=attempt+1, enable_ext_btn2=enable_ext_btn2, is_headless=is_headless)
                page = context.new_page()

                try:
                    for pg in context.pages:
                        if pg != page:
                            try: pg.close()
                            except: pass
                except: pass

                video_tasks[task_id] = {"status": "running", "message": f"Lần thử {attempt+1}/{MAX_RETRIES}: Đang truy cập lại bfl.ai..."}
                page.goto("https://dashboard.bfl.ai/playground?model=flux-3", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                try:
                    existing = page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('video')).map(v => v.src || '').filter(s => s.startsWith('http'));
                    }""")
                    known_video_urls = set(existing or [])
                except: pass

                # Bắt buộc dọn dẹp video cũ trong retry để tránh bắt nhầm
                _clear_old_videos()

                video_tasks[task_id] = {"status": "running", "message": f"Lần thử {attempt+1}/{MAX_RETRIES}: Đang kiểm tra form..."}
                _fill_form(page, context, ext_path, prompt, img1_path, img2_path, video_tasks, task_id, is_retry=True)

            if video_url:
                import urllib.parse
                out_dir = Path(save_path)
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / f"{task_id}.mp4"
                
                try:
                    resp = context.request.get(video_url)
                    if resp.ok:
                        with open(out_file, "wb") as f:
                            f.write(resp.body())
                        all_urls = old_video_urls + [f"/api/video/download/{task_id}?path={urllib.parse.quote(str(out_file))}"]
                        video_tasks[task_id] = {"status": "done", "result_urls": all_urls, "message": "🎉 Video tạo xong!"}
                    else:
                        raise Exception(f"HTTP {resp.status}")
                except Exception as e:
                    video_tasks[task_id] = {"status": "error", "message": f"Tạo thành công nhưng tải video thất bại (BFL.ai chặn download): {e}"}
            else:
                if video_tasks[task_id].get("status") != "error":
                    if old_video_urls:
                        video_tasks[task_id] = {"status": "done", "result_urls": old_video_urls, "message": "Chỉ lấy được video cũ. Job mới thất bại!"}
                    else:
                        video_tasks[task_id] = {"status": "error", "message": "Timeout 10 phút: Video không xuất hiện sau khi GENERATING kết thúc."}

            try: context.close()
            except: pass

    except Exception as e:
        video_tasks[task_id] = {"status": "error", "message": f"Lỗi hệ thống: {e}"}
    
    finally:
        # Tự động xóa ảnh upload sau khi task xong để tiết kiệm dung lượng
        for img_path in [img1_path, img2_path]:
            if img_path:
                try:
                    p = Path(img_path)
                    if p.exists():
                        p.unlink()
                except: pass





@app.post("/api/video/create")
async def create_video(
    prompt: str = Form(...),
    profile_id: str = Form(""),
    img1: UploadFile = File(None),
    img2: UploadFile = File(None),
    save_path: str = Form(None),
    is_headless: str = Form("false"),
    enable_ext_btn2: str = Form("false")
):
    # Lấy danh sách các profile đang bận
    used_profiles = set()
    for task in video_tasks.values():
        if task.get("status") in ["running", "pending"]:
            used_profiles.add(task.get("params", {}).get("profile_id"))
    for p in list_running():
        used_profiles.add(p["id"])

    if not profile_id:
        # Tự động gán profile rảnh
        all_profiles = manager.list_profiles()
        free_profiles = [p for p in all_profiles if p.id not in used_profiles]
        if not free_profiles:
            return JSONResponse(status_code=400, content={"message": "Không còn Profile nào trống. Vui lòng tạo thêm Profile hoặc chờ!"})
        profile_id = free_profiles[0].id
    else:
        # Kiểm tra xem profile được chọn có đang bận không
        if profile_id in used_profiles:
            return JSONResponse(status_code=400, content={"message": "Profile này đang bận (đang mở hoặc đang tạo video khác). Vui lòng chọn profile khác!"})

    headless_bool = (is_headless.lower() == "true")
    task_id = uuid_module.uuid4().hex[:10]
    
    # Save uploaded images
    upload_dir = Path(BASE_DIR) / "data" / "uploads"
    upload_dir.mkdir(exist_ok=True)
    
    img1_path = ""
    if img1 and img1.filename:
        img1_path = str(upload_dir / f"{task_id}_img1{Path(img1.filename).suffix}")
        with open(img1_path, "wb") as f:
            f.write(await img1.read())
    
    img2_path = ""
    if img2 and img2.filename:
        img2_path = str(upload_dir / f"{task_id}_img2{Path(img2.filename).suffix}")
        with open(img2_path, "wb") as f:
            f.write(await img2.read())

    video_tasks[task_id] = {
        "status": "pending", 
        "message": "Đang chuẩn bị...",
        "params": {
            "prompt": prompt,
            "img1_path": img1_path,
            "img2_path": img2_path,
            "profile_id": profile_id,
            "save_path": save_path,
            "is_headless": headless_bool,
            "enable_ext_btn2": (enable_ext_btn2.lower() == "true")
        }
    }
    
    t = threading.Thread(target=run_video_automation, args=(task_id, prompt, img1_path, img2_path, profile_id, save_path, headless_bool, (enable_ext_btn2.lower() == "true")), daemon=True)
    t.start()
    
    return {"ok": True, "task_id": task_id, "profile_id": profile_id}

@app.post("/api/video/retry/{task_id}")
def retry_video(task_id: str):
    task = video_tasks.get(task_id)
    if not task or "params" not in task:
        from fastapi import HTTPException
        raise HTTPException(404, "Task not found")
    
    p = task["params"]
    video_tasks[task_id]["status"] = "pending"
    video_tasks[task_id]["message"] = "Đang thử lại..."
    t = threading.Thread(target=run_video_automation, args=(task_id, p["prompt"], p["img1_path"], p["img2_path"], p["profile_id"], p.get("save_path"), p.get("is_headless", False), p.get("enable_ext_btn2", False)), daemon=True)
    t.start()
    return {"ok": True}

@app.get("/api/video/status/{task_id}")
def video_status(task_id: str):
    return video_tasks.get(task_id, {"status": "not_found"})

from fastapi import Request

@app.get("/api/video/download/{task_id}")
def download_video(task_id: str, request: Request):
    path = request.query_params.get("path")
    if path:
        video_path = Path(path)
    else:
        video_path = Path(BASE_DIR) / "data" / "videos" / f"{task_id}.mp4"
        
    if not video_path.exists():
        raise HTTPException(404, "Video not found")
    from fastapi.responses import FileResponse as FR
    return FR(str(video_path), media_type="video/mp4", filename=video_path.name)



if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Antidetect Tool API running. Go to /docs for API docs"}

if __name__ == "__main__":
    import uvicorn
    print("""
╔══════════════════════════════════════════════════╗
║   Antidetect Unlimited V4 - Full Featured      ║
║   ✅ Cookie Import (BitBrowser format)         ║
║   ✅ Random Fingerprint (giữ cookie)           ║
║   ✅ Tabs persistence (đóng mở vẫn còn)        ║
║   ♾️ Unlimited Profiles                        ║
╚══════════════════════════════════════════════════╝

-> http://localhost:5333
    """)
    uvicorn.run("main:app", host="0.0.0.0", port=5333, reload=False)
