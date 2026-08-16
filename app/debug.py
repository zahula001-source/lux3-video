"""
Debug tool - chạy trực tiếp 1 profile để xem log chi tiết
python -m app.debug <profile_id>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.manager import manager

def debug_launch(profile_id):
    profile = manager.get_profile(profile_id)
    if not profile:
        print("Profile not found")
        return
    
    print(f"Debugging {profile.name} - {profile.browser} - {profile.os}")
    print(f"user_data_dir: {profile.user_data_dir}")
    
    from app.browser import get_camoufox_cache_path, is_camoufox_binary_ready
    print(f"Camoufox cache: {get_camoufox_cache_path()}")
    print(f"Binary ready: {is_camoufox_binary_ready()}")
    
    # Thử import
    try:
        from camoufox.sync_api import Camoufox
        print("Import camoufox.sync_api OK")
    except Exception as e:
        print(f"Import sync_api fail: {e}")
        try:
            from camoufox import Camoufox
            print("Import camoufox OK")
        except Exception as e2:
            print(f"Import camoufox fail: {e2}")
            return
    
    # Thử launch trực tiếp không qua subprocess để thấy lỗi ngay
    kwargs = dict(
        persistent_context=True,
        user_data_dir=profile.user_data_dir,
        headless=False,
    )
    if profile.os != "random":
        kwargs["os"] = profile.os
    
    try:
        print(f"Launching with kwargs: {kwargs}")
        with Camoufox(**kwargs, fingerprint_preset=True) as browser:
            print("SUCCESS! Browser launched")
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://browserleaks.com")
            input("Press Enter to close...")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.debug <profile_id>")
        print("Available profiles:")
        for p in manager.list_profiles():
            print(f"  {p.id} - {p.name}")
    else:
        debug_launch(sys.argv[1])
