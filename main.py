import pygame
import time
import threading
import sys
import os
import argparse
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import win32api
import ctypes
from ctypes import wintypes
from PIL import Image

# Thêm import cho video
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# Windows API constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

# Key codes
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_TAB = 0x09
VK_F4 = 0x73
VK_MENU = 0x12  # Alt key
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_DELETE = 0x2E
VK_ESCAPE = 0x1B

def resource_path(relative_path):
    """
    Lấy đường dẫn tuyệt đối đến resource, dùng cho cả khi chạy script và khi đóng gói exe.
    Ưu tiên thứ tự:
    1) Thư mục tạm của PyInstaller (_MEIPASS)
    2) Thư mục chứa executable (khi đóng gói)
    3) Thư mục làm việc hiện tại
    """
    candidates = []
    try:
        base_meipass = getattr(sys, "_MEIPASS", None)
        if base_meipass:
            candidates.append(os.path.join(base_meipass, relative_path))
    except Exception:
        pass

    try:
        # Thư mục của executable hoặc script
        app_dir = os.path.dirname(getattr(sys, "executable", sys.argv[0]))
        if app_dir:
            candidates.append(os.path.join(os.path.abspath(app_dir), relative_path))
    except Exception:
        pass

    # Thư mục làm việc hiện tại
    candidates.append(os.path.join(os.path.abspath("."), relative_path))

    for p in candidates:
        if os.path.exists(p):
            return p
    # Trả về path ở thư mục làm việc như fallback cuối
    return os.path.join(os.path.abspath("."), relative_path)

def find_default_wallpaper_path():
    """Tìm đường dẫn ảnh wallpaper mặc định ở nhiều vị trí hợp lý khi build exe."""
    names = ["wallpaper.jpg", "wallpaper.jpeg", "wallpaper.png"]
    for name in names:
        p = resource_path(name)
        if os.path.exists(p):
            return p
    return None

def find_vietnamese_font(preferred_fonts=None):
    """
    Tìm font hỗ trợ tiếng Việt trên hệ thống.
    Trả về đường dẫn font hoặc None nếu không tìm thấy.
    """
    import sys
    import os

    if preferred_fonts is None:
        # Arial, Segoe UI, Tahoma, DejaVu Sans đều hỗ trợ Unicode tốt
        preferred_fonts = [
            "arial.ttf", "Arial.ttf", "Arial Unicode.ttf", "arialuni.ttf",
            "segoeui.ttf", "SegoeUI.ttf", "tahoma.ttf", "Tahoma.ttf",
            "DejaVuSans.ttf", "dejavusans.ttf", "times.ttf", "Times.ttf"
        ]

    # Các thư mục font phổ biến trên Windows
    font_dirs = [
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
        "/usr/share/fonts/truetype",
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
    ]

    for font_dir in font_dirs:
        if not os.path.isdir(font_dir):
            continue
        for font_name in preferred_fonts:
            font_path = os.path.join(font_dir, font_name)
            if os.path.isfile(font_path):
                return font_path
    # Nếu không tìm thấy, trả về None
    return None

class PygameScreenProtector:
    def __init__(self, custom_message="", temp_password=None, custom_bg_path=None, target_screen=None, clock_screen=None):
        pygame.init()
        
        # Thiết lập cửa sổ không viền phủ toàn bộ virtual desktop (tất cả màn hình)
        vx, vy, vw, vh = self.get_virtual_desktop_rect()
        # Danh sách monitor với toạ độ tương đối trong virtual desktop
        self.monitors = self.enumerate_monitors(vx, vy, vw, vh)
        self.target_screen = target_screen  # 1-based index từ tham số dòng lệnh
        self.clock_screen = clock_screen  # 1-based index cho vị trí hiển thị clock
        # Xác định phạm vi cửa sổ theo lựa chọn -scr hoặc -clock
        if isinstance(self.target_screen, int) and 1 <= self.target_screen <= len(self.monitors):
            # -scr flag: chỉ khóa một màn hình
            sel = self.monitors[self.target_screen - 1]
            win_x, win_y, win_w, win_h = sel["abs"]
            window_rel_x, window_rel_y = sel["rel"][0], sel["rel"][1]
            self.active_monitors = [sel]
        elif isinstance(self.clock_screen, int) and 1 <= self.clock_screen <= len(self.monitors):
            # -clock flag: khóa tất cả màn hình nhưng chỉ hiển thị UI trên màn hình được chọn
            win_x, win_y, win_w, win_h = vx, vy, vw, vh
            window_rel_x, window_rel_y = 0, 0
            self.active_monitors = self.monitors
        else:
            # Mặc định: khóa tất cả màn hình
            win_x, win_y, win_w, win_h = vx, vy, vw, vh
            window_rel_x, window_rel_y = 0, 0
            self.active_monitors = self.monitors
        # Lưu vị trí cửa sổ trong hệ toạ độ virtual để quy đổi
        self.window_vx, self.window_vy = win_x, win_y
        self.window_rel_x, self.window_rel_y = window_rel_x, window_rel_y
        try:
            os.environ["SDL_VIDEO_WINDOW_POS"] = f"{win_x},{win_y}"
        except Exception:
            pass
        self.screen = pygame.display.set_mode((int(win_w), int(win_h)), pygame.NOFRAME)
        self.width, self.height = int(win_w), int(win_h)
        # Ẩn icon khỏi taskbar và Alt-Tab
        self.hide_from_taskbar()
        self.set_window_topmost_and_place(win_x, win_y, win_w, win_h)
        
        # Thiết lập transparency cho cửa sổ
        self.set_window_transparency()
        
        # Màu sắc
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.TRANSPARENT = (0, 0, 0, 0)
        self.BLUE = (135, 206, 235)
        self.DARK_BLUE = (0, 25, 100)
        
        # Font: Ưu tiên font hỗ trợ tiếng Việt
        self.viet_font_path = find_vietnamese_font()
        if self.viet_font_path:
            try:
                # Giảm size mặc định để tránh tràn frame, nhưng sẽ tự động co lại ở draw_clock
                self.clock_font = pygame.font.Font(self.viet_font_path, 120)
                self.date_font = pygame.font.Font(self.viet_font_path, 60)
                self.password_font = pygame.font.Font(self.viet_font_path, 48)
                self.message_font = pygame.font.Font(self.viet_font_path, 36)
                print(f"✅ Đã sử dụng font hỗ trợ tiếng Việt: {self.viet_font_path}")
            except Exception as e:
                print(f"⚠️ Không thể load font tiếng Việt ({self.viet_font_path}), dùng font mặc định. Lỗi: {e}")
                self.clock_font = pygame.font.Font(None, 120)
                self.date_font = pygame.font.Font(None, 60)
                self.password_font = pygame.font.Font(None, 48)
                self.message_font = pygame.font.Font(None, 36)
        else:
            print("⚠️ Không tìm thấy font tiếng Việt, dùng font mặc định (có thể lỗi dấu).")
            self.clock_font = pygame.font.Font(None, 120)
            self.date_font = pygame.font.Font(None, 60)
            self.password_font = pygame.font.Font(None, 48)
            self.message_font = pygame.font.Font(None, 36)
        
        # Custom message
        self.custom_message = custom_message
        
        # Tạo surface trong suốt cho UI
        self.ui_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        
        # Mật khẩu: sử dụng temp_password nếu có, không thì dùng mặc định
        self.correct_password = temp_password if temp_password else "123456"
        self.password = ""
        self.show_password = False
        self.attempts = 0
        self.max_attempts = 3

        # Hiệu ứng fade và clock move
        self.fade_alpha = 0  # 0-102 (0-40%)
        self.fade_target = 0
        self.clock_y = self.height // 2 - 100
        self.clock_y_target = self.clock_y
        self.clock_move_speed = 18  # px mỗi frame, điều chỉnh cho mượt
        
        # Khởi tạo modifier keys tracking
        self._alt_pressed = False
        self._ctrl_pressed = False
        self._shift_pressed = False
        
        # Khởi động các hook
        self.running = True
        self.start_windows_hook()  # Bật lại Windows API hook
        self.start_keyboard_hook()
        self.start_system_monitor()
        
        # Tải background (ảnh hoặc video)
        self.background_type = None  # "image", "video", hoặc None
        self.background_image = None
        self.video_cap = None
        self.video_frame = None
        self.video_fps = 30
        self.video_last_time = 0
        self.video_path = None
        # Per-monitor assets (khi người dùng cung cấp nhiều background)
        self.monitor_assets = []  # [{type, image, video_cap, video_frame, fps, last_time, path}]

        if custom_bg_path:
            # Cho phép danh sách nhiều đường dẫn, phân tách bằng dấu phẩy
            bg_list = [p.strip() for p in custom_bg_path.split(',') if p.strip()]
            if len(bg_list) > 1:
                self.init_per_monitor_backgrounds(bg_list)
            elif len(bg_list) == 1 and os.path.exists(bg_list[0]):
                single_path = bg_list[0]
                ext = os.path.splitext(single_path)[1].lower()
                if ext in [".mp4", ".avi", ".mov", ".mkv", ".wmv"] and OPENCV_AVAILABLE:
                    self.background_type = "video"
                    self.video_path = single_path
                    self.init_video_background(single_path)
                else:
                    self.background_type = "image"
                    self.background_image = self.load_background_image(single_path)
            else:
                print(f"⚠️ Không tìm thấy file background: {custom_bg_path}")
        else:
            # Nếu không có custom_bg_path hoặc không tồn tại, thử ảnh mặc định
            self.background_image = self.load_background_image(None)
            if self.background_image:
                self.background_type = "image"
            else:
                self.background_type = None

        # Validate clock screen if specified
        if self.clock_screen is not None:
            if self.clock_screen < 1 or self.clock_screen > len(self.monitors):
                print(f"❌ Lỗi: Số màn hình clock ({self.clock_screen}) không hợp lệ. Có {len(self.monitors)} màn hình.")
                sys.exit(1)
            
            # Hiển thị thông tin chi tiết về màn hình được chọn
            target_monitor = self.monitors[self.clock_screen - 1]
            abs_x, abs_y, abs_w, abs_h = target_monitor["abs"]
            center_x = abs_x + abs_w // 2
            center_y = abs_y + abs_h // 2
            print(f"🕐 Đồng hồ sẽ hiển thị trên màn hình {self.clock_screen}")
            print(f"   Màn hình {self.clock_screen}: {abs_w}x{abs_h} tại vị trí ({abs_x},{abs_y})")
            print(f"   Vị trí center: ({center_x}, {center_y})")
        
        print("✅ Pygame Screen Protector đã khởi động thành công!")
        print(f"📱 Kích thước cửa sổ: {self.width}x{self.height}")
        print(f"🖥️  Phát hiện {len(self.monitors)} màn hình:")
        for i, mon in enumerate(self.monitors):
            abs_x, abs_y, abs_w, abs_h = mon["abs"]
            print(f"   Màn hình {i+1}: {abs_w}x{abs_h} tại vị trí ({abs_x},{abs_y})")
        if self.custom_message:
            print(f"💬 Custom message: {self.custom_message}")
        if temp_password:
            print(f"🔑 Sử dụng mật khẩu tạm thời: {temp_password}")
        else:
            print(f"🔑 Sử dụng mật khẩu mặc định: {self.correct_password}")
        if custom_bg_path:
            print(f"🖼️  Sử dụng background tạm thời: {custom_bg_path}")
        if self.background_type == "video":
            print(f"🎬 Đang sử dụng video làm background: {self.video_path}")
        elif self.background_type == "image":
            print(f"🖼️  Đang sử dụng ảnh làm background.")
        elif self.monitor_assets:
            print(f"🖥️  Đang sử dụng nền per-monitor: {len(self.active_monitors)} màn hình (đang khoá {'màn hình ' + str(self.target_screen) if self.target_screen else 'tất cả'})")
        else:
            print(f"🌈 Sử dụng gradient background.")

    def get_virtual_desktop_rect(self):
        """Lấy toạ độ và kích thước virtual desktop (bao gồm tất cả màn hình)."""
        try:
            # Chỉ số System Metrics cho virtual screen trên Windows
            SM_XVIRTUALSCREEN = 76
            SM_YVIRTUALSCREEN = 77
            SM_CXVIRTUALSCREEN = 78
            SM_CYVIRTUALSCREEN = 79
            vx = win32api.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = win32api.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = win32api.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = win32api.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            return vx, vy, vw, vh
        except Exception:
            # Fallback: dùng kích thước màn hình hiện tại
            info = pygame.display.Info()
            return 0, 0, info.current_w, info.current_h

    def set_window_topmost_and_place(self, x, y, w, h):
        """Đặt cửa sổ luôn-on-top và đúng vị trí virtual desktop."""
        try:
            hwnd = pygame.display.get_wm_info().get('window')
            if hwnd:
                HWND_TOPMOST = -1
                SWP_SHOWWINDOW = 0x0040
                ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), int(w), int(h), SWP_SHOWWINDOW)
        except Exception:
            pass

    def set_window_transparency(self):
        """Thiết lập transparency cho cửa sổ Pygame"""
        # Không cần thiết lập transparency cho toàn bộ cửa sổ
        # Chỉ UI elements sẽ có transparency
        pass

    def hide_from_taskbar(self):
        """Ẩn cửa sổ khỏi taskbar (và Alt+Tab) bằng cách chỉnh extended window styles."""
        try:
            hwnd = pygame.display.get_wm_info().get('window')
            if not hwnd:
                return
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            exstyle = (exstyle | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)
            # Áp dụng thay đổi khung
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                              SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW)
        except Exception:
            pass

    def enumerate_monitors(self, vx, vy, vw, vh):
        """Trả về danh sách các màn hình với rect tương đối (x,y,w,h) so với virtual desktop."""
        monitors = []
        try:
            user32 = ctypes.windll.user32
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(RECT), ctypes.c_double)
            def _callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                r = lprcMonitor.contents
                mx, my, mw, mh = r.left, r.top, r.right - r.left, r.bottom - r.top
                monitors.append({
                    "abs": (mx, my, mw, mh),
                    "rel": (mx - vx, my - vy, mw, mh)
                })
                return 1
            MonitorEnumProc_cb = MonitorEnumProc(_callback)
            user32.EnumDisplayMonitors(0, 0, MonitorEnumProc_cb, 0)
            if not monitors:
                raise RuntimeError("No monitors enumerated")
        except Exception:
            monitors = [{"abs": (vx, vy, vw, vh), "rel": (0, 0, vw, vh)}]
        return monitors

    def init_per_monitor_backgrounds(self, bg_list):
        """Khởi tạo tài nguyên nền cho từng monitor theo danh sách đường dẫn."""
        self.monitor_assets = []
        for idx, mon in enumerate(self.monitors):
            path = bg_list[idx % len(bg_list)]
            asset = {"type": None, "image": None, "video_cap": None, "video_frame": None, "fps": 30, "last_time": 0.0, "path": path}
            if os.path.exists(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in [".mp4", ".avi", ".mov", ".mkv", ".wmv"] and OPENCV_AVAILABLE:
                    try:
                        cap = cv2.VideoCapture(path)
                        if cap.isOpened():
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            asset["type"], asset["video_cap"], asset["fps"] = "video", cap, fps if fps and fps > 1 else 30
                        else:
                            cap.release()
                    except Exception:
                        pass
                if asset["type"] is None:
                    # Fallback image
                    try:
                        _, _, mw, mh = mon["rel"]
                        pil_image = Image.open(path)
                        pil_image = pil_image.resize((int(mw), int(mh)), Image.Resampling.LANCZOS)
                        mode = pil_image.mode
                        size = pil_image.size
                        data = pil_image.tobytes()
                        asset["image"] = pygame.image.fromstring(data, size, mode)
                        asset["type"] = "image"
                    except Exception:
                        asset["type"] = None
            self.monitor_assets.append(asset)

    def get_next_video_frame_for(self, asset, mw, mh):
        """Đọc frame tiếp theo từ asset video, resize theo (mw,mh), trả về surface hoặc None."""
        cap = asset.get("video_cap")
        if not cap:
            return None
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret:
                return None
        frame = cv2.resize(frame, (int(mw), int(mh)))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return pygame.surfarray.make_surface(frame.swapaxes(0, 1))

    def draw_clock_at(self, center_x, center_y):
        """Vẽ một khối đồng hồ + ngày + message tại vị trí center chỉ định."""
        glass_width = 500
        glass_height = 250
        clock_glass = self.create_glass_effect(0, 0, glass_width, glass_height, 40, (255, 255, 255))
        clock_rect = clock_glass.get_rect(center=(int(center_x), int(center_y)))
        current_time = time.strftime("%H:%M")
        current_date = time.strftime("%A, %B %d")
        max_time_width = int(glass_width * 0.9)
        max_time_height = int(glass_height * 0.4)
        time_surface, _ = self._render_text_fit(self.clock_font, current_time, max_time_width, self.WHITE, min_font_size=36, max_height=max_time_height)
        time_rect = time_surface.get_rect(center=(glass_width//2, 100))
        max_date_width = int(glass_width * 0.9)
        max_date_height = int(glass_height * 0.2)
        date_surface, _ = self._render_text_fit(self.date_font, current_date, max_date_width, self.WHITE, min_font_size=20, max_height=max_date_height)
        date_rect = date_surface.get_rect(center=(glass_width//2, 170))
        clock_glass.blit(time_surface, time_rect)
        clock_glass.blit(date_surface, date_rect)
        if self.custom_message:
            max_msg_width = int(glass_width * 0.9)
            max_msg_height = int(glass_height * 0.2)
            msg_surface, _ = self._render_text_fit(self.message_font, self.custom_message, max_msg_width, self.WHITE, min_font_size=16, max_height=max_msg_height)
            msg_rect = msg_surface.get_rect(center=(glass_width//2, 220))
            clock_glass.blit(msg_surface, msg_rect)
        self.ui_surface.blit(clock_glass, clock_rect)

    def init_video_background(self, video_path):
        """Khởi tạo video background"""
        try:
            self.video_cap = cv2.VideoCapture(video_path)
            if not self.video_cap.isOpened():
                print(f"❌ Không thể mở video: {video_path}")
                self.background_type = None
                self.video_cap = None
                return
            # Lấy fps của video
            fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            if fps and fps > 1:
                self.video_fps = fps
            else:
                self.video_fps = 30
            print(f"🎬 Đã mở video background: {video_path} (fps={self.video_fps})")
        except Exception as e:
            print(f"❌ Lỗi khi mở video background: {e}")
            self.background_type = None
            self.video_cap = None

    def get_next_video_frame(self):
        """Lấy frame tiếp theo từ video, trả về pygame.Surface hoặc None"""
        if not self.video_cap:
            return None
        ret, frame = self.video_cap.read()
        if not ret:
            # Nếu hết video, tua lại từ đầu
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.video_cap.read()
            if not ret:
                return None
        # Resize frame về kích thước màn hình
        frame = cv2.resize(frame, (self.width, self.height))
        # Chuyển BGR -> RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Tạo surface từ numpy array
        surf = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
        return surf

    def load_background_image(self, custom_bg_path=None):
        """Tải background image, ưu tiên custom_bg_path nếu có"""
        try:
            img_path = None
            if custom_bg_path:
                if os.path.exists(custom_bg_path):
                    img_path = custom_bg_path
                else:
                    print(f"⚠️ Không tìm thấy file background tạm thời: {custom_bg_path}")
            if not img_path:
                # Tìm ảnh mặc định ở nhiều vị trí (hỗ trợ PyInstaller)
                default_path = find_default_wallpaper_path()
                if default_path:
                    img_path = default_path
            if img_path:
                # Tải và resize image
                pil_image = Image.open(img_path)
                pil_image = pil_image.resize((self.width, self.height), Image.Resampling.LANCZOS)
                
                # Chuyển sang Pygame surface
                mode = pil_image.mode
                size = pil_image.size
                data = pil_image.tobytes()
                
                pygame_image = pygame.image.fromstring(data, size, mode)
                print(f"✅ Đã tải background image: {img_path}")
                return pygame_image
            else:
                print(f"⚠️ Không tìm thấy background image, sử dụng gradient")
                return None
        except Exception as e:
            print(f"❌ Lỗi tải background: {e}")
            return None

    def create_gradient_background(self):
        """Tạo gradient background đẹp"""
        gradient_surface = pygame.Surface((self.width, self.height))
        
        for y in range(self.height):
            ratio = y / self.height
            if ratio < 0.5:  # Nửa trên - xanh trời
                r = int(135 + (200 - 135) * (ratio * 2))
                g = int(206 + (230 - 206) * (ratio * 2))
                b = int(235 + (255 - 235) * (ratio * 2))
            else:  # Nửa dưới - xanh biển sâu
                r = int(0 + (25 - 0) * ((ratio - 0.5) * 2))
                g = int(25 + (50 - 25) * ((ratio - 0.5) * 2))
                b = int(100 + (150 - 100) * ((ratio - 0.5) * 2))
            
            pygame.draw.line(gradient_surface, (r, g, b), (0, y), (self.width, y))
        
        return gradient_surface

    def create_glass_effect(self, x, y, width, height, alpha=100, color=(255, 255, 255)):
        """Tạo hiệu ứng glass morphism với transparency thực sự"""
        glass_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # Tạo nền trong suốt với độ mờ nhẹ
        # Sử dụng alpha thấp để tạo hiệu ứng trong suốt
        glass_color = (*color, alpha)
        pygame.draw.rect(glass_surface, glass_color, (0, 0, width, height), border_radius=20)
        
        # Thêm viền trong suốt để tạo hiệu ứng glass
        border_color = (*color, alpha // 2)
        pygame.draw.rect(glass_surface, border_color, (0, 0, width, height), width=2, border_radius=20)
        
        return glass_surface

    def draw_fade_overlay(self):
        """Vẽ lớp fade mờ lên background khi show_password"""
        if self.fade_alpha > 0:
            fade_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            fade_surface.fill((0, 0, 0, self.fade_alpha))
            self.screen.blit(fade_surface, (0, 0))

    def _render_text_fit(self, font, text, max_width, color, min_font_size=12, max_height=None):
        """
        Render text to fit within max_width (and optionally max_height). 
        If too long, shrink font size or truncate with ellipsis.
        Returns: (surface, used_font)
        """
        # Try to shrink font size if possible
        font_size = font.get_height()
        orig_font_path = font.get_name() if hasattr(font, "get_name") else None
        while font_size >= min_font_size:
            test_font = pygame.font.Font(self.viet_font_path if self.viet_font_path else None, font_size)
            text_surface = test_font.render(text, True, color)
            if text_surface.get_width() <= max_width and (max_height is None or text_surface.get_height() <= max_height):
                return text_surface, test_font
            font_size -= 2
        # If still too long, truncate and add ellipsis
        test_font = pygame.font.Font(self.viet_font_path if self.viet_font_path else None, min_font_size)
        ellipsis = "..."
        max_text = text
        while len(max_text) > 0:
            test_surface = test_font.render(max_text + ellipsis, True, color)
            if test_surface.get_width() <= max_width and (max_height is None or test_surface.get_height() <= max_height):
                return test_surface, test_font
            max_text = max_text[:-1]
        # Fallback: just render ellipsis
        return test_font.render(ellipsis, True, color), test_font

    def draw_clock(self):
        """Vẽ đồng hồ với nền trong suốt, tự động co chữ cho vừa frame"""
        current_time = time.strftime("%H:%M")
        current_date = time.strftime("%A, %B %d")
        
        # Xóa surface cũ
        self.ui_surface.fill(self.TRANSPARENT)
        
        # Tạo hiệu ứng glass cho đồng hồ - nền trong suốt
        glass_width = 500
        glass_height = 250
        clock_glass = self.create_glass_effect(0, 0, glass_width, glass_height, 40, (255, 255, 255))
        clock_rect = clock_glass.get_rect(center=(self.width//2, int(self.clock_y)))
        
        # Tự động fit text cho vừa frame
        # Thời gian: chiếm tối đa 90% width, 40% height
        max_time_width = int(glass_width * 0.9)
        max_time_height = int(glass_height * 0.4)
        time_surface, time_font = self._render_text_fit(self.clock_font, current_time, max_time_width, self.WHITE, min_font_size=36, max_height=max_time_height)
        time_rect = time_surface.get_rect(center=(glass_width//2, 100))
        
        # Ngày: chiếm tối đa 90% width, 20% height
        max_date_width = int(glass_width * 0.9)
        max_date_height = int(glass_height * 0.2)
        date_surface, date_font = self._render_text_fit(self.date_font, current_date, max_date_width, self.WHITE, min_font_size=20, max_height=max_date_height)
        date_rect = date_surface.get_rect(center=(glass_width//2, 170))
        
        clock_glass.blit(time_surface, time_rect)
        clock_glass.blit(date_surface, date_rect)
        
        # Vẽ custom message nếu có, xử lý quá dài
        if self.custom_message:
            # Giới hạn chiều rộng message là 90% glass_width, tối đa 20% chiều cao
            max_msg_width = int(glass_width * 0.9)
            max_msg_height = int(glass_height * 0.2)
            msg_surface, msg_font = self._render_text_fit(self.message_font, self.custom_message, max_msg_width, self.WHITE, min_font_size=16, max_height=max_msg_height)
            msg_rect = msg_surface.get_rect(center=(glass_width//2, 220))
            clock_glass.blit(msg_surface, msg_rect)
        
        # Vẽ glass lên UI surface
        self.ui_surface.blit(clock_glass, clock_rect)
    
    def draw_password_field(self):
        """Vẽ ô mật khẩu với nền trong suốt"""
        # Kích thước nhỏ hơn, giống màn hình lock của Windows
        pw_width = 280
        pw_height = 60
        pw_glass = self.create_glass_effect(0, 0, pw_width, pw_height, 80, (0, 0, 0))
        pw_rect = pw_glass.get_rect(center=(self.width//2, self.height//2 + 150))
        
        # Vẽ password (dấu *)
        password_display = "*" * len(self.password)
        # Font nhỏ hơn cho phù hợp với ô nhỏ
        pw_text = self.password_font.render(password_display, True, self.WHITE)
        pw_text_rect = pw_text.get_rect(center=(pw_width//2, pw_height//2))
        pw_glass.blit(pw_text, pw_text_rect)
        
        # Vẽ glass lên UI surface
        self.ui_surface.blit(pw_glass, pw_rect)
    
    def draw_password_field_at(self, center_x, center_y):
        """Vẽ ô mật khẩu tại vị trí center chỉ định"""
        # Kích thước nhỏ hơn, giống màn hình lock của Windows
        pw_width = 280
        pw_height = 60
        pw_glass = self.create_glass_effect(0, 0, pw_width, pw_height, 80, (0, 0, 0))
        pw_rect = pw_glass.get_rect(center=(int(center_x), int(center_y)))
        
        # Vẽ password (dấu *)
        password_display = "*" * len(self.password)
        # Font nhỏ hơn cho phù hợp với ô nhỏ
        pw_text = self.password_font.render(password_display, True, self.WHITE)
        pw_text_rect = pw_text.get_rect(center=(pw_width//2, pw_height//2))
        pw_glass.blit(pw_text, pw_text_rect)
        
        # Vẽ glass lên UI surface
        self.ui_surface.blit(pw_glass, pw_rect)
    
    def run(self):
        """Vòng lặp chính"""
        clock = pygame.time.Clock()
        # Hiệu ứng fade và clock move
        FADE_MAX = int(255 * 0.4)  # 40% alpha ~ 102
        CLOCK_Y_NORMAL = self.height // 2 - 100
        CLOCK_Y_UP = self.height // 2 - 220  # Di chuyển lên trên
        
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Khi click chuột, show_password = True, fade lên, clock move lên
                    if not self.show_password:
                        self.show_password = True
                        self.fade_target = FADE_MAX
                        self.clock_y_target = CLOCK_Y_UP
                        print("🔓 Hiện ô mật khẩu - hiệu ứng fade và đồng hồ di chuyển lên")
                    else:
                        self.show_password = False
                        self.fade_target = 0
                        self.clock_y_target = CLOCK_Y_NORMAL
                        print("🔒 Ẩn ô mật khẩu - hiệu ứng fade biến mất, đồng hồ về vị trí cũ")
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_ESCAPE:
                        if self.show_password:
                            self.show_password = False
                            self.fade_target = 0
                            self.clock_y_target = CLOCK_Y_NORMAL
                            print("🔒 Ẩn ô mật khẩu")
            
            # Cập nhật hiệu ứng fade alpha
            if self.fade_alpha < self.fade_target:
                self.fade_alpha = min(self.fade_alpha + 10, self.fade_target)
            elif self.fade_alpha > self.fade_target:
                self.fade_alpha = max(self.fade_alpha - 10, self.fade_target)
            
            # Cập nhật vị trí đồng hồ mượt mà
            if self.clock_y < self.clock_y_target:
                self.clock_y = min(self.clock_y + self.clock_move_speed, self.clock_y_target)
            elif self.clock_y > self.clock_y_target:
                self.clock_y = max(self.clock_y - self.clock_move_speed, self.clock_y_target)
            
            # Vẽ background (per-monitor nếu có), sau đó UI per-monitor
            if self.monitor_assets:
                for idx, mon in enumerate(self.active_monitors):
                    rx, ry, mw, mh = mon["rel"]
                    # Khi chỉ khoá một màn hình, toạ độ rel phải quy đổi về (0,0) trong cửa sổ
                    if len(self.active_monitors) == 1:
                        rx, ry = 0, 0
                    asset = self.monitor_assets[idx] if idx < len(self.monitor_assets) else None
                    if asset and asset.get("type") == "video" and asset.get("video_cap"):
                        now = time.time()
                        interval = 1.0 / asset.get("fps", 30)
                        if now - asset.get("last_time", 0) >= interval:
                            asset["video_frame"] = self.get_next_video_frame_for(asset, mw, mh)
                            asset["last_time"] = now
                        if asset.get("video_frame") is not None:
                            self.screen.blit(asset["video_frame"], (int(rx), int(ry)))
                        else:
                            pygame.draw.rect(self.screen, (0, 0, 0), pygame.Rect(int(rx), int(ry), int(mw), int(mh)))
                    elif asset and asset.get("type") == "image" and asset.get("image"):
                        self.screen.blit(asset["image"], (int(rx), int(ry)))
                    else:
                        # Gradient fill region
                        sub_surface = pygame.Surface((int(mw), int(mh)))
                        # Simple vertical gradient in region
                        for y in range(int(mh)):
                            ratio = y / max(1, mh)
                            if ratio < 0.5:
                                r = int(135 + (200 - 135) * (ratio * 2))
                                g = int(206 + (230 - 206) * (ratio * 2))
                                b = int(235 + (255 - 235) * (ratio * 2))
                            else:
                                r = int(0 + (25 - 0) * ((ratio - 0.5) * 2))
                                g = int(25 + (50 - 25) * ((ratio - 0.5) * 2))
                                b = int(100 + (150 - 100) * ((ratio - 0.5) * 2))
                            pygame.draw.line(sub_surface, (r, g, b), (0, y), (int(mw), y))
                        self.screen.blit(sub_surface, (int(rx), int(ry)))
            elif self.background_type == "video" and self.video_cap:
                # Tính toán thời gian để lấy frame tiếp theo
                now = time.time()
                interval = 1.0 / self.video_fps if self.video_fps > 0 else 1.0 / 30
                if now - self.video_last_time >= interval:
                    self.video_frame = self.get_next_video_frame()
                    self.video_last_time = now
                if self.video_frame is not None:
                    self.screen.blit(self.video_frame, (0, 0))
                else:
                    # Nếu không lấy được frame, dùng gradient
                    gradient = self.create_gradient_background()
                    self.screen.blit(gradient, (0, 0))
            elif self.background_type == "image" and self.background_image:
                self.screen.blit(self.background_image, (0, 0))
            else:
                gradient = self.create_gradient_background()
                self.screen.blit(gradient, (0, 0))
            
            # Vẽ lớp fade nếu cần
            self.draw_fade_overlay()
            
            # Vẽ UI với transparency
            self.ui_surface.fill(self.TRANSPARENT)
            if self.monitor_assets:
                # Một clock giữa mỗi monitor
                for idx, mon in enumerate(self.active_monitors):
                    rx, ry, mw, mh = mon["rel"]
                    if len(self.active_monitors) == 1:
                        rx, ry = 0, 0
                    
                    # Logic hiển thị clock dựa trên các flag
                    should_show_clock = False
                    if self.clock_screen is not None:
                        # Nếu có -clock flag, hiển thị clock trên màn hình được chỉ định
                        if self.clock_screen == idx + 1:  # Convert to 1-based index
                            should_show_clock = True
                    elif self.target_screen is not None:
                        # Nếu có -scr flag, hiển thị clock trên màn hình được chọn
                        if self.target_screen == idx + 1:  # Convert to 1-based index
                            should_show_clock = True
                    else:
                        # Mặc định: hiển thị clock trên màn hình đầu tiên
                        if idx == 0:
                            should_show_clock = True
                    
                    if should_show_clock:
                        # Tính toán vị trí center chính xác cho màn hình này
                        # Sử dụng tọa độ tuyệt đối của màn hình để tính center chính xác
                        abs_x, abs_y, abs_w, abs_h = mon["abs"]
                        center_x = abs_x + abs_w // 2
                        
                        if self.clock_screen is not None:
                            # Khi dùng -clock, tính center_y dựa trên màn hình được chọn
                            center_y = abs_y + abs_h // 2 - 100  # Giữa màn hình, hơi lên trên
                        else:
                            # Logic cũ cho các trường hợp khác
                            center_y = abs_y + (self.clock_y - (self.height // 2 - 100))
                            center_y = max(abs_y + 100, min(abs_y + abs_h - 100, center_y))
                        
                        # Chuyển đổi từ tọa độ tuyệt đối về tọa độ tương đối trong cửa sổ
                        window_center_x = center_x - self.window_vx
                        window_center_y = center_y - self.window_vy
                        
                        self.draw_clock_at(window_center_x, window_center_y)
                        
                        # Vẽ password field nếu cần (chỉ trên màn hình hiển thị clock)
                        if self.show_password or self.fade_alpha > 0:
                            self.draw_password_field_at(window_center_x, window_center_y + 200)  # Dưới clock 200px
            else:
                # Trường hợp không có monitor_assets, vẫn cần hỗ trợ -clock flag
                if self.clock_screen is not None and 1 <= self.clock_screen <= len(self.monitors):
                    # Hiển thị clock trên màn hình được chọn
                    target_monitor = self.monitors[self.clock_screen - 1]
                    abs_x, abs_y, abs_w, abs_h = target_monitor["abs"]
                    
                    # Tính center chính xác dựa trên tọa độ tuyệt đối
                    center_x = abs_x + abs_w // 2
                    center_y = abs_y + abs_h // 2 - 100  # Giữa màn hình, hơi lên trên
                    
                    # Chuyển đổi từ tọa độ tuyệt đối về tọa độ tương đối trong cửa sổ
                    window_center_x = center_x - self.window_vx
                    window_center_y = center_y - self.window_vy
                    
                    self.draw_clock_at(window_center_x, window_center_y)
                    
                    # Vẽ password field nếu cần
                    if self.show_password or self.fade_alpha > 0:
                        self.draw_password_field_at(window_center_x, window_center_y + 200)  # Dưới clock 200px
                else:
                    # Logic cũ cho trường hợp mặc định
                    self.draw_clock()
                    # Vẽ password field nếu cần (cho trường hợp mặc định)
                    if self.show_password or self.fade_alpha > 0:
                        self.draw_password_field()
            self.screen.blit(self.ui_surface, (0, 0))
            
            pygame.display.flip()
            clock.tick(60)
        
        # Thoát mượt mà
        print("🔄 Đang đóng Pygame...")
        # Giải phóng video nếu có
        if self.video_cap:
            self.video_cap.release()
        pygame.quit()
        print("✅ Ứng dụng đã thoát thành công!")
        # Không gọi sys.exit() để tránh "refresh" màn hình
    
    def handle_keydown(self, event):
        """Xử lý phím nhấn"""
        # Chỉ xử lý nhập mật khẩu khi ô mật khẩu đang hiển thị
        if not self.show_password:
            return
            
        if event.key == pygame.K_RETURN:
            self.check_password()
        elif event.key == pygame.K_BACKSPACE:
            self.password = self.password[:-1]
        elif event.unicode.isprintable():
            if len(self.password) < 20:  # Giới hạn độ dài
                self.password += event.unicode
    
    def check_password(self):
        """Kiểm tra mật khẩu"""
        if self.password == self.correct_password:
            print("✅ Mật khẩu đúng! Mở khóa màn hình...")
            self.unlock_screen()
        else:
            self.attempts += 1
            remaining_attempts = self.max_attempts - self.attempts
            
            if remaining_attempts > 0:
                print(f"❌ Mật khẩu sai! Còn {remaining_attempts} lần thử.")
            else:
                print("❌ Đã vượt quá số lần thử cho phép!")
                self.attempts = 0
            
            self.password = ""
    
    def unlock_screen(self):
        """Mở khóa màn hình"""
        print("🔓 Mở khóa màn hình...")
        
        # Dừng các hook
        if hasattr(self, 'keyboard_listener') and self.keyboard_listener:
            self.keyboard_listener.stop()
        if hasattr(self, 'hook_id') and self.hook_id:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
        
        # Thoát mượt mà - không gọi iconify để tránh "refresh" màn hình
        print("🔄 Đang thoát ứng dụng...")
        self.running = False
    
    def start_windows_hook(self):
        """Khởi động Windows API keyboard hook"""
        try:
            def keyboard_proc(nCode, wParam, lParam):
                if nCode >= 0:
                    if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                        try:
                            vk_code = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong)).contents.value & 0xFF
                            
                            # Chặn Windows key
                            if vk_code in [VK_LWIN, VK_RWIN]:
                                print("🚫 Chặn Windows key bằng Windows API")
                                return 1
                            
                            # Chặn Alt+F4
                            if vk_code == VK_F4 and win32api.GetAsyncKeyState(VK_MENU) & 0x8000:
                                print("🚫 Chặn Alt+F4 bằng Windows API")
                                return 1
                            
                            # Chặn Alt+Tab
                            if vk_code == VK_TAB and win32api.GetAsyncKeyState(VK_MENU) & 0x8000:
                                print("🚫 Chặn Alt+Tab bằng Windows API")
                                return 1
                            
                            # Chặn Ctrl+Alt+Del
                            if vk_code == VK_DELETE:
                                if (win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000 and 
                                    win32api.GetAsyncKeyState(VK_MENU) & 0x8000):
                                    print("🚫 Chặn Ctrl+Alt+Del bằng Windows API")
                                    return 1
                            
                            # Chặn Ctrl+Shift+Esc
                            if vk_code == VK_ESCAPE:
                                if (win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000 and 
                                    win32api.GetAsyncKeyState(VK_SHIFT) & 0x8000):
                                    print("🚫 Chặn Ctrl+Shift+Esc bằng Windows API")
                                    return 1
                                
                        except Exception as e:
                            print(f"❌ Lỗi xử lý phím trong hook: {e}")
                
                try:
                    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
                except:
                    return 0
            
            HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))
            self.keyboard_proc = HOOKPROC(keyboard_proc)
            
            # Thử nhiều cách để cài đặt hook
            module_handle = ctypes.windll.kernel32.GetModuleHandleW(None)
            self.hook_id = ctypes.windll.user32.SetWindowsHookExA(
                WH_KEYBOARD_LL,
                self.keyboard_proc,
                module_handle,
                0
            )
            
            if self.hook_id:
                print("✅ Windows API keyboard hook đã được cài đặt thành công!")
                print(f"   Hook ID: {self.hook_id}")
            else:
                print("❌ Không thể cài đặt Windows API keyboard hook")
                error_code = ctypes.windll.kernel32.GetLastError()
                print(f"   Error code: {error_code}")
                
                # Thử cách khác - sử dụng None cho module handle
                print("🔄 Thử cách khác - sử dụng None cho module handle...")
                try:
                    self.hook_id = ctypes.windll.user32.SetWindowsHookExA(
                        WH_KEYBOARD_LL,
                        self.keyboard_proc,
                        None,  # Sử dụng None thay vì module handle
                        0
                    )
                    
                    if self.hook_id:
                        print("✅ Windows API keyboard hook đã được cài đặt thành công (cách 2)!")
                        print(f"   Hook ID: {self.hook_id}")
                    else:
                        print("❌ Vẫn không thể cài đặt hook")
                        error_code = ctypes.windll.kernel32.GetLastError()
                        print(f"   Error code: {error_code}")
                        
                except Exception as e2:
                    print(f"❌ Lỗi khi thử cách 2: {e2}")
                
        except Exception as e:
            print(f"❌ Lỗi khi cài đặt Windows API hook: {e}")
            import traceback
            traceback.print_exc()
    
    def start_keyboard_hook(self):
        """Khởi động hook bàn phím pynput (backup)"""
        try:
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release,
                suppress=False  # Không suppress để Windows API hook làm việc chính
            )
            self.keyboard_listener.start()
            print("✅ Pynput keyboard hook đã được khởi động (backup)!")
        except Exception as e:
            print(f"❌ Không thể khởi động pynput keyboard hook: {e}")
    
    def on_key_press(self, key):
        """Xử lý khi nhấn phím"""
        try:
            # Chỉ cho phép nhập mật khẩu khi ô mật khẩu đang hiển thị
            if not self.show_password:
                return False

            # Chặn các phím tắt hệ thống nguy hiểm
            if self.is_dangerous_key_combination(key):
                print(f"🚫 Chặn phím tắt hệ thống: {key}")
                return False
            
            # Cho phép các phím cần thiết cho nhập mật khẩu
            if self.is_allowed_key(key):
                return True
            
            # Chặn tất cả các phím khác
            return False
        except Exception as e:
            print(f"❌ Lỗi xử lý phím: {e}")
            return False
    
    def is_dangerous_key_combination(self, key):
        """Kiểm tra xem có phải phím tắt hệ thống nguy hiểm không"""
        # Chặn Windows key
        if key == Key.cmd or key == Key.cmd_r:
            return True
        
        # Chặn Alt+F4
        if hasattr(self, '_alt_pressed') and self._alt_pressed and key == Key.f4:
            return True
        
        # Chặn Alt+Tab
        if hasattr(self, '_alt_pressed') and self._alt_pressed and key == Key.tab:
            return True
        
        # Chặn Ctrl+Alt+Del
        if hasattr(self, '_ctrl_pressed') and self._ctrl_pressed and \
           hasattr(self, '_alt_pressed') and self._alt_pressed and key == Key.delete:
            return True
        
        # Chặn Ctrl+Shift+Esc
        if hasattr(self, '_ctrl_pressed') and self._ctrl_pressed and \
           hasattr(self, '_shift_pressed') and self._shift_pressed and key == Key.esc:
            return True
        
        return False
    
    def on_key_release(self, key):
        """Xử lý khi thả phím"""
        try:
            # Theo dõi modifier keys để chặn phím tắt
            if key == Key.alt:
                self._alt_pressed = False
            elif key == Key.ctrl:
                self._ctrl_pressed = False
            elif key == Key.shift:
                self._shift_pressed = False
        except Exception as e:
            print(f"❌ Lỗi xử lý phím release: {e}")
    
    def on_key_press(self, key):
        """Xử lý khi nhấn phím"""
        try:
            # Theo dõi modifier keys
            if key == Key.alt:
                self._alt_pressed = True
            elif key == Key.ctrl:
                self._ctrl_pressed = True
            elif key == Key.shift:
                self._shift_pressed = True
            
            # Chặn các phím tắt hệ thống nguy hiểm
            if self.is_dangerous_key_combination(key):
                print(f"🚫 Chặn phím tắt hệ thống: {key}")
                return False
            
            # Cho phép các phím cần thiết cho nhập mật khẩu
            if self.is_allowed_key(key):
                return True
            
            # Chặn tất cả các phím khác
            return False
        except Exception as e:
            print(f"❌ Lỗi xử lý phím: {e}")
            return False
    
    def is_allowed_key(self, key):
        """Kiểm tra xem có phải phím được phép không"""
        if hasattr(key, 'char') and key.char:
            return True
        
        allowed_keys = [
            Key.backspace, Key.delete, Key.left, Key.right, 
            Key.up, Key.down, Key.home, Key.end, Key.enter,
            Key.tab, Key.space
        ]
        
        if key in allowed_keys:
            return True
        
        return False
    
    def start_system_monitor(self):
        """Khởi động thread giám sát phím tắt hệ thống"""
        def monitor():
            while self.running:
                try:
                    # Chặn Alt+Tab
                    if win32api.GetAsyncKeyState(VK_TAB) & 0x8000:
                        if win32api.GetAsyncKeyState(VK_MENU) & 0x8000:
                            print("🚫 Chặn Alt+Tab (backup)")
                            time.sleep(0.001)
                            continue
                    
                    # Chặn Alt+F4
                    if win32api.GetAsyncKeyState(VK_F4) & 0x8000:
                        if win32api.GetAsyncKeyState(VK_MENU) & 0x8000:
                            print("🚫 Chặn Alt+F4 (backup)")
                            time.sleep(0.001)
                            continue
                    
                    # Chặn Windows key
                    if win32api.GetAsyncKeyState(VK_LWIN) & 0x8000 or \
                       win32api.GetAsyncKeyState(VK_RWIN) & 0x8000:
                        print("🚫 Chặn Windows key (backup)")
                        time.sleep(0.001)
                        continue
                    
                    # Chặn Ctrl+Alt+Del
                    if win32api.GetAsyncKeyState(VK_DELETE) & 0x8000:
                        if (win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000 and 
                            win32api.GetAsyncKeyState(VK_MENU) & 0x8000):
                            print("🚫 Chặn Ctrl+Alt+Del (backup)")
                            time.sleep(0.001)
                            continue
                    
                    time.sleep(0.001)
                    
                except Exception as e:
                    print(f"❌ Lỗi giám sát phím: {e}")
                    time.sleep(0.1)
        
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        print("✅ System monitor thread đã được khởi động!")

def main():
    """Hàm chính"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Pygame Screen Protector')
    parser.add_argument('-msg', '--message', type=str, default='', 
                       help='Custom message to display below the clock')
    parser.add_argument('-pw', '--password', type=str, default=None,
                       help='Temporary password to unlock the screen (default: 123456)')
    parser.add_argument('-bg', '--background', type=str, default=None,
                       help='Đường dẫn file ảnh hoặc video background tạm thời cho lần khóa này (hỗ trợ .mp4, .avi, .mov, .mkv, .wmv)')
    parser.add_argument('-scr', '--screen', type=int, default=None,
                       help='Chỉ khoá một màn hình (1-based). Bỏ qua để khoá tất cả.')
    parser.add_argument('-clock', '--clock', type=int, default=None,
                       help='Hiển thị đồng hồ và ô nhập mật khẩu ở màn hình được chọn (1-based). Khóa tất cả màn hình nhưng chỉ hiển thị UI trên màn hình được chọn.')
    args = parser.parse_args()
    
    # Validate clock screen parameter
    if args.clock is not None and args.clock < 1:
        print("❌ Lỗi: Số màn hình phải >= 1")
        sys.exit(1)
    
    print("🚀 Khởi động Pygame Screen Protector...")
    print("🔑 Mật khẩu mặc định: 123456")
    print("🎮 Click chuột để hiện/ẩn ô mật khẩu")
    print("⌨️  Nhấn Enter để xác nhận mật khẩu")
    print("🛡️  Đã bật chế độ bảo vệ chặn phím tắt hệ thống!")
    if args.message:
        print(f"💬 Custom message: {args.message}")
    if args.password:
        print(f"🔑 Sử dụng mật khẩu tạm thời: {args.password}")
    else:
        print(f"🔑 Sử dụng mật khẩu mặc định: 123456")
    if args.background:
        print(f"🖼️  Sử dụng background tạm thời: {args.background}")
        ext = os.path.splitext(args.background)[1].lower()
        if ext in [".mp4", ".avi", ".mov", ".mkv", ".wmv"]:
            if not OPENCV_AVAILABLE:
                print("⚠️  Bạn cần cài đặt opencv-python để sử dụng video làm background: pip install opencv-python")
            else:
                print("🎬 Sử dụng video làm background (beta)")
    if args.clock:
        print(f"🕐 Hiển thị đồng hồ trên màn hình: {args.clock}")
    print("=" * 50)
    
    try:
        app = PygameScreenProtector(args.message, args.password, args.background, args.screen, args.clock)
        app.run()
    except Exception as e:
        print(f"❌ Lỗi khởi động ứng dụng: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
