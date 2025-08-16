import tkinter as tk
from tkinter import messagebox
import threading
import time
import sys
import os
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import win32api
import win32con
import win32gui
import ctypes
from ctypes import wintypes

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

class ScreenProtector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screen Protector")
        
        # Thiết lập fullscreen và luôn ở trên cùng
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)  # Ẩn thanh tiêu đề
        
        # Thiết lập màu nền đen
        self.root.configure(bg='black')
        
        # Tạo frame chính
        self.main_frame = tk.Frame(self.root, bg='black')
        self.main_frame.pack(expand=True, fill='both')
        
        # Tạo label hiển thị thông báo
        self.message_label = tk.Label(
            self.main_frame,
            text="Màn hình đã được khóa\nVui lòng nhập mật khẩu để mở khóa",
            font=('Arial', 24, 'bold'),
            fg='white',
            bg='black',
            justify='center'
        )
        self.message_label.pack(expand=True)
        
        # Tạo frame cho mật khẩu
        self.password_frame = tk.Frame(self.main_frame, bg='black')
        self.password_frame.pack(pady=50)
        
        # Label cho mật khẩu
        self.password_label = tk.Label(
            self.password_frame,
            text="Mật khẩu:",
            font=('Arial', 16),
            fg='white',
            bg='black'
        )
        self.password_label.pack()
        
        # Entry cho nhập mật khẩu
        self.password_entry = tk.Entry(
            self.password_frame,
            font=('Arial', 16),
            show='*',
            width=20
        )
        self.password_entry.pack(pady=10)
        self.password_entry.focus()
        
        # Nút đăng nhập
        self.login_button = tk.Button(
            self.password_frame,
            text="Đăng nhập",
            font=('Arial', 14),
            command=self.check_password,
            bg='#4CAF50',
            fg='white',
            relief='flat',
            padx=20,
            pady=10
        )
        self.login_button.pack(pady=10)
        
        # Nút thoát
        self.exit_button = tk.Button(
            self.password_frame,
            text="Thoát",
            font=('Arial', 14),
            command=self.exit_app,
            bg='#f44336',
            fg='white',
            relief='flat',
            padx=20,
            pady=10
        )
        self.exit_button.pack(pady=5)
        
        # Mật khẩu mặc định (có thể thay đổi)
        self.correct_password = "123456"
        
        # Bind phím Enter để đăng nhập
        self.password_entry.bind('<Return>', lambda event: self.check_password())
        
        # Bind phím Escape để thoát
        self.root.bind('<Escape>', lambda event: self.exit_app())
        
        # Thiết lập focus cho entry
        self.password_entry.focus_set()
        
        # Biến để theo dõi số lần thử sai
        self.attempts = 0
        self.max_attempts = 3
        
        # Khởi tạo keyboard listener
        self.keyboard_listener = None
        self.running = True
        
        # Bind focus events để quản lý hook
        self.password_entry.bind('<FocusIn>', self.on_password_focus_in)
        self.password_entry.bind('<FocusOut>', self.on_password_focus_out)
        
        # Khởi động Windows API hook trước
        self.start_windows_hook()
        
        # Khởi động thread giám sát phím tắt hệ thống
        self.monitor_thread = threading.Thread(target=self.monitor_system_keys, daemon=True)
        self.monitor_thread.start()
        
        # Khởi động keyboard hook
        self.start_keyboard_hook()
        
        # Bind sự kiện đóng cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def start_windows_hook(self):
        """Khởi động Windows API keyboard hook"""
        try:
            # Định nghĩa callback function với đúng kiểu dữ liệu
            def keyboard_proc(nCode, wParam, lParam):
                if nCode >= 0:
                    if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                        try:
                            # Lấy virtual key code từ lParam - sửa lỗi kiểu dữ liệu
                            vk_code = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong)).contents.value & 0xFF
                            
                            # Chặn Windows key
                            if vk_code in [VK_LWIN, VK_RWIN]:
                                print("🚫 Chặn Windows key bằng Windows API")
                                return 1  # Chặn phím
                            
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
                
                # Gọi hook tiếp theo - sửa lỗi kiểu dữ liệu
                try:
                    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
                except:
                    return 0
            
            # Định nghĩa kiểu dữ liệu cho callback
            HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))
            
            # Tạo callback function với đúng kiểu
            self.keyboard_proc = HOOKPROC(keyboard_proc)
            
            # Lấy module handle của process hiện tại
            current_pid = os.getpid()
            module_handle = ctypes.windll.kernel32.GetModuleHandleW(None)
            
            print(f"🔍 Process ID: {current_pid}")
            print(f"🔍 Module Handle: {module_handle}")
            
            # Cài đặt hook với đúng kiểu dữ liệu
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
                
                # Thử cách khác - sử dụng hook đơn giản hơn
                print("🔄 Thử cách khác - sử dụng hook đơn giản...")
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
        """Khởi động hook bàn phím pynput"""
        try:
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release,
                suppress=True  # Chặn hoàn toàn các phím
            )
            self.keyboard_listener.start()
            print("✅ Pynput keyboard hook đã được khởi động!")
        except Exception as e:
            print(f"❌ Không thể khởi động pynput keyboard hook: {e}")
    
    def on_key_press(self, key):
        """Xử lý khi nhấn phím"""
        try:
            # Cho phép các phím cần thiết cho nhập mật khẩu
            if self.is_allowed_key(key):
                return True
            
            # Chặn tất cả các phím khác
            return False
        except Exception as e:
            print(f"❌ Lỗi xử lý phím: {e}")
            return False
    
    def on_key_release(self, key):
        """Xử lý khi thả phím"""
        pass
    
    def is_allowed_key(self, key):
        """Kiểm tra xem có phải phím được phép không"""
        # Cho phép các phím chữ và số
        if hasattr(key, 'char') and key.char:
            return True
        
        # Cho phép các phím điều hướng cơ bản
        allowed_keys = [
            Key.backspace, Key.delete, Key.left, Key.right, 
            Key.up, Key.down, Key.home, Key.end, Key.enter,
            Key.tab, Key.space
        ]
        
        if key in allowed_keys:
            return True
        
        return False
    
    def monitor_system_keys(self):
        """Giám sát và chặn phím tắt hệ thống (backup mạnh hơn)"""
        while self.running:
            try:
                # Chặn Alt+Tab - cải thiện
                if win32api.GetAsyncKeyState(VK_TAB) & 0x8000:
                    if win32api.GetAsyncKeyState(VK_MENU) & 0x8000:  # Alt key
                        print("🚫 Chặn Alt+Tab (backup mạnh)")
                        # Chặn liên tục để đảm bảo không thể bypass
                        time.sleep(0.001)  # Delay cực nhỏ để chặn triệt để
                        continue
                
                # Chặn Alt+F4 - cải thiện
                if win32api.GetAsyncKeyState(VK_F4) & 0x8000:
                    if win32api.GetAsyncKeyState(VK_MENU) & 0x8000:  # Alt key
                        print("🚫 Chặn Alt+F4 (backup mạnh)")
                        time.sleep(0.001)
                        continue
                
                # Chặn Windows key - cải thiện
                if win32api.GetAsyncKeyState(VK_LWIN) & 0x8000 or \
                   win32api.GetAsyncKeyState(VK_RWIN) & 0x8000:
                    print("🚫 Chặn Windows key (backup mạnh)")
                    time.sleep(0.001)
                    continue
                
                # Chặn Ctrl+Alt+Del - cải thiện
                if win32api.GetAsyncKeyState(VK_DELETE) & 0x8000:
                    if (win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000 and 
                        win32api.GetAsyncKeyState(VK_MENU) & 0x8000):
                        print("🚫 Chặn Ctrl+Alt+Del (backup mạnh)")
                        time.sleep(0.001)
                        continue
                
                # Chặn Ctrl+Shift+Esc - cải thiện
                if win32api.GetAsyncKeyState(VK_ESCAPE) & 0x8000:
                    if (win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000 and 
                        win32api.GetAsyncKeyState(VK_SHIFT) & 0x8000):
                        print("🚫 Chặn Ctrl+Shift+Esc (backup mạnh)")
                        time.sleep(0.001)
                        continue
                
                # Chặn thêm các phím tắt khác
                # Chặn Alt+Space (menu cửa sổ)
                if win32api.GetAsyncKeyState(0x20) & 0x8000:  # Space key
                    if win32api.GetAsyncKeyState(VK_MENU) & 0x8000:  # Alt key
                        print("🚫 Chặn Alt+Space (backup mạnh)")
                        time.sleep(0.001)
                        continue
                
                # Chặn F11 (fullscreen)
                if win32api.GetAsyncKeyState(0x7A) & 0x8000:  # F11 key
                    print("🚫 Chặn F11 (backup mạnh)")
                    time.sleep(0.001)
                    continue
                
                # Chặn Ctrl+W (đóng tab/cửa sổ)
                if win32api.GetAsyncKeyState(0x57) & 0x8000:  # W key
                    if win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000:
                        print("🚫 Chặn Ctrl+W (backup mạnh)")
                        time.sleep(0.001)
                        continue
                
                # Chặn Ctrl+Q (thoát ứng dụng)
                if win32api.GetAsyncKeyState(0x51) & 0x8000:  # Q key
                    if win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000:
                        print("🚫 Chặn Ctrl+Q (backup mạnh)")
                        time.sleep(0.001)
                        continue
                
                # Chặn Ctrl+Shift+N (tạo mới)
                if win32api.GetAsyncKeyState(0x4E) & 0x8000:  # N key
                    if (win32api.GetAsyncKeyState(VK_CONTROL) & 0x8000 and 
                        win32api.GetAsyncKeyState(VK_SHIFT) & 0x8000):
                        print("🚫 Chặn Ctrl+Shift+N (backup mạnh)")
                        time.sleep(0.001)
                        continue
                
                time.sleep(0.001)  # Delay cực nhỏ để chặn triệt để
                
            except Exception as e:
                print(f"❌ Lỗi giám sát phím: {e}")
                time.sleep(0.1)
    
    def on_closing(self):
        """Xử lý khi đóng cửa sổ"""
        print("🚫 Cố gắng đóng cửa sổ - bị chặn!")
        return "break"  # Ngăn không cho đóng
    
    def on_password_focus_in(self, event):
        """Khi focus vào ô mật khẩu"""
        print("✅ Focus vào ô mật khẩu - cho phép nhập liệu")
    
    def on_password_focus_out(self, event):
        """Khi không focus vào ô mật khẩu"""
        print("🔒 Không focus vào ô mật khẩu - bật hook bảo vệ")
    
    def check_password(self):
        """Kiểm tra mật khẩu"""
        entered_password = self.password_entry.get()
        
        if entered_password == self.correct_password:
            messagebox.showinfo("Thành công", "Mật khẩu đúng! Màn hình sẽ được mở khóa.")
            self.unlock_screen()
        else:
            self.attempts += 1
            remaining_attempts = self.max_attempts - self.attempts
            
            if remaining_attempts > 0:
                messagebox.showerror("Lỗi", f"Mật khẩu sai! Còn {remaining_attempts} lần thử.")
                self.password_entry.delete(0, tk.END)
                self.password_entry.focus()
            else:
                messagebox.showerror("Lỗi", "Đã vượt quá số lần thử cho phép!")
                self.password_entry.delete(0, tk.END)
                self.attempts = 0  # Reset số lần thử
    
    def unlock_screen(self):
        """Mở khóa màn hình"""
        print("🔓 Mở khóa màn hình...")
        self.running = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if hasattr(self, 'hook_id') and self.hook_id:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
        self.root.destroy()
        sys.exit()
    
    def exit_app(self):
        """Thoát ứng dụng"""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn thoát?"):
            print("🚪 Thoát ứng dụng...")
            self.running = False
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            if hasattr(self, 'hook_id') and self.hook_id:
                ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            self.root.destroy()
            sys.exit()
    
    def run(self):
        """Chạy ứng dụng"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("🛑 Nhận tín hiệu thoát...")
            self.running = False
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            if hasattr(self, 'hook_id') and self.hook_id:
                ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)
            self.root.destroy()
            sys.exit()

def main():
    """Hàm chính"""
    print("🚀 Khởi động Screen Protector...")
    print("🔑 Mật khẩu mặc định: 123456")
    print("⌨️  Nhấn Ctrl+C để thoát")
    print("🛡️  Đã bật chế độ bảo vệ chặn phím tắt hệ thống!")
    print("=" * 50)
    
    # Tạo và chạy ứng dụng
    app = ScreenProtector()
    app.run()

if __name__ == "__main__":
    main()
