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
    """
    try:
        # PyInstaller tạo biến _MEIPASS khi chạy exe
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

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
    def __init__(self, custom_message="", temp_password=None):
        pygame.init()
        
        # Thiết lập màn hình fullscreen
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.width, self.height = self.screen.get_size()
        
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
        
        # Tải background image
        self.background_image = self.load_background_image()
        
        print("✅ Pygame Screen Protector đã khởi động thành công!")
        print(f"📱 Kích thước màn hình: {self.width}x{self.height}")
        if self.custom_message:
            print(f"💬 Custom message: {self.custom_message}")
        if temp_password:
            print(f"🔑 Sử dụng mật khẩu tạm thời: {temp_password}")
        else:
            print(f"🔑 Sử dụng mật khẩu mặc định: {self.correct_password}")
        
    def set_window_transparency(self):
        """Thiết lập transparency cho cửa sổ Pygame"""
        # Không cần thiết lập transparency cho toàn bộ cửa sổ
        # Chỉ UI elements sẽ có transparency
        pass
    
    def load_background_image(self):
        """Tải background image"""
        try:
            # Sử dụng resource_path để lấy đúng đường dẫn khi build exe
            img_path = resource_path("wallpaper.jpg")
            if os.path.exists(img_path):
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
                print(f"⚠️ Không tìm thấy {img_path}, sử dụng gradient")
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
        
        # Vẽ password field nếu cần
        if self.show_password or self.fade_alpha > 0:
            self.draw_password_field()
    
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
            
            # Vẽ background
            if self.background_image:
                self.screen.blit(self.background_image, (0, 0))
            else:
                gradient = self.create_gradient_background()
                self.screen.blit(gradient, (0, 0))
            
            # Vẽ lớp fade nếu cần
            self.draw_fade_overlay()
            
            # Vẽ UI với transparency
            self.draw_clock()
            self.screen.blit(self.ui_surface, (0, 0))
            
            pygame.display.flip()
            clock.tick(60)
        
        # Thoát mượt mà
        print("🔄 Đang đóng Pygame...")
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
    args = parser.parse_args()
    
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
    print("=" * 50)
    
    try:
        app = PygameScreenProtector(args.message, args.password)
        app.run()
    except Exception as e:
        print(f"❌ Lỗi khởi động ứng dụng: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
