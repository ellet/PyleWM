import ctypes as c
import ctypes.wintypes as w

WS_SIZEBOX = 0x00040000
WS_MINIMIZE = 0x20000000
WS_MAXIMIZE = 0x01000000
WS_CAPTION = 0x00C00000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
WS_DISABLED = 0x08000000
WS_DLGFRAME = 0x00400000
WS_BORDER = 0x00800000
WS_POPUP = 0x80000000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00200000
WS_MAXIMIZEBOX = 0x00010000
WS_OVERLAPPEDWINDOW = WS_CAPTION | WS_SYSMENU | WS_SIZEBOX | WS_MINIMIZEBOX | WS_MAXIMIZEBOX

tEnumWindowFunc = c.CFUNCTYPE(None, w.HWND, w.LPARAM)

EnumWindows = c.WINFUNCTYPE(
    w.BOOL,
    tEnumWindowFunc, w.LPARAM
)(("EnumWindows", c.windll.user32))

GetWindowTextW = c.WINFUNCTYPE(
    c.c_int,
    w.HWND, w.LPWSTR, c.c_int,
)(("GetWindowTextW", c.windll.user32))

GetWindowTextLengthW = c.WINFUNCTYPE(
    c.c_int,
    w.HWND,
)(("GetWindowTextLengthW", c.windll.user32))

def WindowGetTitle(hwnd):
    length = GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = c.create_unicode_buffer(length+1)
    GetWindowTextW(hwnd, buffer, length+1)
    return buffer.value

GetClassNameW = c.WINFUNCTYPE(
    c.c_int,
    w.HWND, w.LPWSTR, c.c_int,
)(("GetClassNameW", c.windll.user32))

GetClassNameLengthW = c.WINFUNCTYPE(
    c.c_int,
    w.HWND, w.LPWSTR, c.c_int,
)(("GetClassNameW", c.windll.user32))

def WindowGetClass(hwnd):
    buffer = c.create_unicode_buffer(256)
    GetClassNameW(hwnd, buffer, c.sizeof(buffer))
    return buffer.value

IsWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND,
)(("IsWindow", c.windll.user32))

IsWindowVisible = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND,
)(("IsWindowVisible", c.windll.user32))

GetWindowLongA = c.WINFUNCTYPE(
    w.LONG,
    w.HWND, c.c_int,
)(("GetWindowLongA", c.windll.user32))

SetWindowLongA = c.WINFUNCTYPE(
    w.LONG,
    w.HWND, c.c_int, w.LONG,
)(("SetWindowLongA", c.windll.user32))

GWL_EXSTYLE = -20
def WindowGetExStyle(hwnd):
    return GetWindowLongA(hwnd, GWL_EXSTYLE)

GWL_STYLE = -16
def WindowGetStyle(hwnd):
    return GetWindowLongA(hwnd, GWL_STYLE)

def WindowSetStyle(hwnd, style):
    return SetWindowLongA(hwnd, GWL_STYLE, style)

GetWindowLongPtrW = c.WINFUNCTYPE(
    w.HANDLE,
    w.HWND, c.c_int,
)(("GetWindowLongPtrW", c.windll.user32))

GWL_HWNDPARENT = -8
def WindowIsChild(hwnd):
    return IsWindow(GetWindowLongPtrW(hwnd, GWL_HWNDPARENT))

def GetWindowParent(hwnd):
    return GetWindowLongPtrW(hwnd, GWL_HWNDPARENT)

DwmGetWindowAttribute = c.WINFUNCTYPE(
    None,
    w.HWND, w.DWORD, c.c_void_p, w.DWORD,
)(("DwmGetWindowAttribute", c.windll.dwmapi))

DWMWA_CLOAKED = 14
def WindowIsCloaked(hwnd):
    output = (c.c_uint * 1)()
    DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, output, 4)
    return output[0] != 0

GetWindowRect = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND, c.POINTER(w.RECT),
)(("GetWindowRect", c.windll.user32))

AdjustWindowRectEx = c.WINFUNCTYPE(
    w.BOOL,
    c.POINTER(w.RECT), c.c_uint, c.c_bool, c.c_uint,
)(("AdjustWindowRectEx", c.windll.user32))

SetWindowPos = c.WINFUNCTYPE(
    w.BOOL,

    w.HWND, # Window Handle
    w.HWND, # Insert after Window
    c.c_int, # X
    c.c_int, # Y
    c.c_int, # cx
    c.c_int, # cy
    w.UINT, # uFlags
)(("SetWindowPos", c.windll.user32))

HWND_BOTTOM = 1
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SW_SHOW = 5
SW_SHOWNOACTIVATE = 4
SW_FORCEMINIMIZE = 11
SW_RESTORE = 9
SW_HIDE = 0

SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOOWNERZORDER = 0x0200
SWP_SHOWWINDOW = 0x0040
SWP_ASYNCWINDOWPOS = 0x4000
SWP_NOREDRAW = 0x0008
SWP_DEFERERASE = 0x2000
SWP_NOCOPYBITS = 0x0100

GetForegroundWindow = c.WINFUNCTYPE(
    w.HWND,
)(("GetForegroundWindow", c.windll.user32))

SetForegroundWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND,
)(("SetForegroundWindow", c.windll.user32))

SetCursorPos = c.WINFUNCTYPE(
    w.BOOL,
    c.c_int, c.c_int,
)(("SetCursorPos", c.windll.user32))

GetCursorPos = c.WINFUNCTYPE(
    w.BOOL,
    w.LPPOINT,
)(("GetCursorPos", c.windll.user32))

GetShellWindow = c.WINFUNCTYPE(
    w.HWND,
)(("GetShellWindow", c.windll.user32))

IsHungAppWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND,
)(("IsHungAppWindow", c.windll.user32))

ShowWindowAsync = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND, c.c_int,
)(("ShowWindowAsync", c.windll.user32))

ShowWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND, c.c_int,
)(("ShowWindow", c.windll.user32))

WM_CLOSE = 0x0010

PostMessageW = c.WINFUNCTYPE(
    w.BOOL,

    w.HWND, # Window Handle
    w.UINT, # Message Type
    w.WPARAM, # wParam
    w.LPARAM, # lParam
)(("PostMessageW", c.windll.user32))

MessageBoxW = c.WINFUNCTYPE(
    c.c_int,

    w.HWND, # Parent Window Handle
    w.LPCWSTR, # Text
    w.LPCWSTR, # Caption
    w.UINT, # uType
)(("MessageBoxW", c.windll.user32))

def ShowMessageBox(title, content):
    MessageBoxW(None, content, title, 0)

GetAsyncKeyState = c.WINFUNCTYPE(
    w.SHORT,
    c.c_int,
)(("GetAsyncKeyState", c.windll.user32))

tEnumDisplayMonitorFunc = c.CFUNCTYPE(w.BOOL, w.HMONITOR, w.HDC, c.POINTER(w.RECT), w.LPARAM)

EnumDisplayMonitors = c.WINFUNCTYPE(
    w.BOOL,
    w.HDC, c.POINTER(w.RECT), tEnumDisplayMonitorFunc, w.LPARAM,
)(("EnumDisplayMonitors", c.windll.user32))

class MONITORINFO(c.Structure):
    _fields_ = (
        ('cbSize',          w.DWORD),
        ('rcMonitor',       w.RECT),
        ('rcWork',          w.RECT),
        ('dwFlags',         w.DWORD),
    )

    def __init__(self):
        self.cbSize = c.sizeof(MONITORINFO)

GetMonitorInfoW = c.WINFUNCTYPE(
    w.BOOL,
    w.HMONITOR, c.POINTER(MONITORINFO),
)(("GetMonitorInfoW", c.windll.user32))

LRESULT = c.c_int64
HOOKPROC = c.CFUNCTYPE(LRESULT, w.INT, w.WPARAM, w.LPARAM)

SetWindowsHookExW = c.WINFUNCTYPE(
    w.HHOOK,
    w.INT, HOOKPROC, w.HINSTANCE, w.DWORD
)(("SetWindowsHookExW", c.windll.user32))

GetModuleHandleW = c.WINFUNCTYPE(
    w.HMODULE,
    w.LPCWSTR,
)(("GetModuleHandleW", c.windll.kernel32))

UnhookWindowsHookEx = c.WINFUNCTYPE(
    w.BOOL,
    w.HHOOK,
)(("UnhookWindowsHookEx", c.windll.user32))

CallNextHookEx = c.WINFUNCTYPE(
    LRESULT,
    w.HHOOK, w.INT, w.WPARAM, w.LPARAM,
)(("CallNextHookEx", c.windll.user32))

class KBDLLHOOKSTRUCT(c.Structure):
    _fields_ = (
        ('vkCode',          w.DWORD),
        ('scanCode',        w.DWORD),
        ('flags',           w.DWORD),
        ('time',            w.DWORD),
        ('dwExtraInfo',     c.POINTER(w.ULONG)),
    )

def CastToKbDllHookStruct(lParam):
    return c.cast(lParam, c.POINTER(KBDLLHOOKSTRUCT))[0]

GetMessageW = c.WINFUNCTYPE(
    w.BOOL,
    w.LPMSG, w.HWND, w.UINT, w.UINT,
)(("GetMessageW", c.windll.user32))

PM_NOREMOVE = 0x0
PM_REMOVE = 0x1
PM_NOYIELD = 0x2
PeekMessageW = c.WINFUNCTYPE(
    w.BOOL,
    w.LPMSG, w.HWND, w.UINT, w.UINT, w.UINT,
)(("PeekMessageW", c.windll.user32))

TranslateMessage = c.WINFUNCTYPE(
    w.BOOL,
    w.LPMSG,
)(("TranslateMessage", c.windll.user32))

DispatchMessageW = c.WINFUNCTYPE(
    LRESULT,
    w.LPMSG,
)(("DispatchMessageW", c.windll.user32))

ShellExecuteW = c.WINFUNCTYPE(
    w.HINSTANCE,
    w.HWND, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, c.c_int,
)(("ShellExecuteW", c.windll.shell32))

WindowFromPoint = c.WINFUNCTYPE(
    w.HWND,
    w.POINT,
)(("WindowFromPoint", c.windll.user32))

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 1
KEYEVENTF_KEYUP = 2
KEYEVENTF_UNICODE = 4
KEYEVENTF_SCANCODE = 8

class MOUSEINPUT(c.Structure):
    _fields_ = [
        ('dx', w.LONG),
        ('dy', w.LONG),
        ('mouseData', w.DWORD),
        ('dwFlags', w.DWORD),
        ('time', w.DWORD),
        ('dwExtraInfo', c.c_ulonglong),
    ]

class KEYBDINPUT(c.Structure):
    _fields_ = [
        ('wVk', w.WORD),
        ('wScan', w.WORD),
        ('dwFlags', w.DWORD),
        ('time', w.DWORD),
        ('dwExtraInfo', c.c_ulonglong),
    ]

class HARDWAREINPUT(c.Structure):
    _fields_ = [
        ('uMsg', w.DWORD),
        ('wParamL', w.WORD),
        ('wParamH', w.WORD),
    ]

class DUMMYUNIONNAME(c.Union):
    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
        ('hi', HARDWAREINPUT),
    ]

class INPUT(c.Structure):
    _fields_ = [
        ('type', w.DWORD),
        ('DUMMYUNIONNAME', DUMMYUNIONNAME),
    ]

SendInput = c.WINFUNCTYPE(
    w.UINT,
    w.UINT, c.POINTER(INPUT), c.c_int,
)(("SendInput", c.windll.user32))

WNDPROC = c.WINFUNCTYPE(
    c.c_int,
    w.HWND, w.UINT, w.WPARAM, w.LPARAM
)

class WNDCLASSEX(c.Structure):
    _fields_ = [
        ("cbSize", c.c_uint),
        ("style", c.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", c.c_int),
        ("cbWndExtra", c.c_int),
        ("hInstance", w.HANDLE),
        ("hIcon", w.HANDLE),
        ("hCursor", w.HANDLE),
        ("hBrush", w.HANDLE),
        ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR),
        ("hIconSm", w.HANDLE),
    ]

CS_HREDRAW = 2
CS_VREDRAW = 1

CloseWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND,
)(("CloseWindow", c.windll.user32))

DestroyWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND,
)(("DestroyWindow", c.windll.user32))

CreateWindowExW = c.WINFUNCTYPE(
    w.HWND,
    w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
    c.c_int, c.c_int,
    c.c_int, c.c_int,
    w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID
)(("CreateWindowExW", c.windll.user32))

UpdateWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND,
)(("UpdateWindow", c.windll.user32))

RedrawWindow = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND, c.POINTER(w.RECT), w.HRGN, c.c_uint,
)(("RedrawWindow", c.windll.user32))

InvalidateRect = c.WINFUNCTYPE(
    w.BOOL,
    w.HWND, c.POINTER(w.RECT), w.BOOL,
)(("InvalidateRect", c.windll.user32))

DefWindowProcW = c.WINFUNCTYPE(
    c.c_int,
    w.HWND, c.c_uint, w.WPARAM, w.LPARAM,
)(("DefWindowProcW", c.windll.user32))

class PAINTSTRUCT(c.Structure):
    _fields_ = [
        ("hdc", w.HDC),
        ("fErase", w.BOOL),
        ("rcPaint", w.RECT),
        ("fRestore", w.BOOL),
        ("fIncUpdate", w.BOOL),
        ("rgbReserved", w.BYTE*32),
    ]

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

def GetExecutableOfWindow(hwnd):
    try:
        dwProcId = w.DWORD()
        c.windll.user32.GetWindowThreadProcessId(hwnd, c.pointer(dwProcId))
        procHandle = c.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, dwProcId)

        buffer = c.create_unicode_buffer(1024)
        length = w.DWORD(1024)

        c.windll.kernel32.QueryFullProcessImageNameW(procHandle, 0, buffer, c.pointer(length))
        c.windll.kernel32.CloseHandle(procHandle)
        return buffer.value
    except:
        return ""

GetLastError = c.WINFUNCTYPE(
    w.DWORD,
)(("GetLastError", c.windll.kernel32))