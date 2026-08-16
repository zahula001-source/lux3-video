"""
Fingerprint generator - sạch, nhẹ, chuẩn logic như BitBrowser
Dùng BrowserForge nếu có, fallback về random logic
"""
import random
from typing import Dict, Any

# Real-world distribution like Camoufox does
OS_WEIGHTS = {
    "windows": 0.72,
    "macos": 0.18,
    "linux": 0.10
}

WINDOWS_VERSIONS = ["10", "11"]
RESOLUTIONS = {
    "windows": ["1920x1080", "2560x1440", "1366x768", "1536x864", "1440x900", "2560x1080"],
    "macos": ["1440x900", "2560x1440", "1920x1080", "1680x1050", "1280x800"],
    "linux": ["1920x1080", "1366x768", "2560x1440", "1280x1024"]
}

GPU_BY_OS = {
    "windows": [
        "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11-31.0.15.3640)",
        "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11-32.0.15.5585)",
        "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11-27.20.100.8681)",
        "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0, D3D11-31.0.12027.1000)"
    ],
    "macos": [
        "ANGLE (Apple, Apple M1, OpenGL 4.1)",
        "ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)",
        "ANGLE (Apple, Apple M2, OpenGL 4.1)",
        "ANGLE (Intel Inc., Intel(R) Iris(TM) Graphics 6100, OpenGL 4.1)"
    ],
    "linux": [
        "ANGLE (NVIDIA, NVIDIA GeForce GTX 1050 Ti/PCIe/SSE2, OpenGL 4.5.0)",
        "Mesa DRI Intel(R) UHD Graphics 620 (Kabylake GT2)",
        "ANGLE (Intel, Mesa Intel(R) UHD Graphics 630 (CFL GT2), OpenGL 4.6)"
    ]
}

def try_browserforge_fingerprint(os_choice: str = "windows"):
    """Thử dùng browserforge để gen fingerprint thật"""
    try:
        from browserforge.fingerprints import FingerprintGenerator
        from browserforge.headers import HeaderGenerator
        fg = FingerprintGenerator(
            browser=("chrome", "firefox"),
            os=(os_choice if os_choice != "random" else None),
            device="desktop"
        )
        fingerprint = fg.generate()
        hg = HeaderGenerator(
            browser=("chrome", "firefox"),
            os=(os_choice if os_choice != "random" else None)
        )
        headers = hg.generate()
        return {
            "browserforge": True,
            "fingerprint": fingerprint,
            "headers": headers
        }
    except Exception as e:
        # fallback
        return None

def generate_fingerprint(os_choice: str = "random") -> Dict[str, Any]:
    if os_choice == "random":
        os_choice = random.choices(
            list(OS_WEIGHTS.keys()),
            weights=list(OS_WEIGHTS.values())
        )[0]

    browserforge_data = try_browserforge_fingerprint(os_choice)
    if browserforge_data:
        # merge with our simplified structure
        return {
            "os": os_choice,
            "browserforge": browserforge_data,
            "screen": random.choice(RESOLUTIONS.get(os_choice, RESOLUTIONS["windows"])),
            "gpu": random.choice(GPU_BY_OS.get(os_choice, GPU_BY_OS["windows"])),
            "webrtc": "disabled",
            "canvas_noise": True,
            "audio_noise": True
        }

    # Fallback pure random - vẫn đảm bảo logic consistency
    resolution = random.choice(RESOLUTIONS.get(os_choice, RESOLUTIONS["windows"]))
    gpu = random.choice(GPU_BY_OS.get(os_choice, GPU_BY_OS["windows"]))
    
    return {
        "os": os_choice,
        "screen": resolution,
        "gpu": gpu,
        "navigator": {
            "platform": "Win32" if os_choice == "windows" else "MacIntel" if os_choice == "macos" else "Linux x86_64",
            "hardwareConcurrency": random.choice([4, 8, 12, 16]),
            "deviceMemory": random.choice([4, 8, 16]),
            "languages": ["en-US", "en"],
            "timezone": "Asia/Ho_Chi_Minh" if random.random() > 0.5 else "UTC"
        },
        "webrtc": "disabled",
        "canvas_noise": random.uniform(0.0001, 0.001),
        "webgl_noise": random.uniform(0.0001, 0.001),
        "audio_noise": True,
        "font_list": "realistic"
    }

def get_proxy_dict(proxy):
    if not proxy:
        return None
    # Playwright format: {"server": "http://ip:port", "username": ..., "password": ...}
    server = f"{proxy.type}://{proxy.host}:{proxy.port}"
    d = {"server": server}
    if proxy.username:
        d["username"] = proxy.username
    if proxy.password:
        d["password"] = proxy.password
    return d
