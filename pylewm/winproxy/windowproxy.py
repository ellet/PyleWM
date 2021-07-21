import pylewm.winproxy.winfuncs as winfuncs
from pylewm.commands import CommandQueue, Commands
from pylewm.rects import Rect

from threading import Lock
import functools

WindowProxyLock = Lock()
WindowsByHandle : dict[int, 'WindowProxy'] = dict()
ProxyCommands = CommandQueue()

WS_SIZEBOX = 0x00040000
WS_MINIMIZE = 0x20000000
WS_MAXIMIZE = 0x01000000
WS_CAPTION = 0x00C00000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000

class WindowInfo:
    def __init__(self):
        self.window_title = ""
        self.window_class = ""
        self.visible = False
        self.cloaked = False
        self.is_child = False
        self.is_hung = False
        self.rect = Rect()
        self._winStyle = 0
        self._exStyle = 0

    def set(self, other : 'WindowInfo'):
        self.window_title = other.window_title
        self.window_class = other.window_class
        self.visible = other.visible
        self.cloaked = other.cloaked
        self.is_child = other.is_child
        self.is_hung = other.is_hung
        self.rect.assign(other.rect)
        self._winStyle = other._winStyle
        self._exStyle = other._exStyle

    def can_resize(self):
        return (self._winStyle & WS_SIZEBOX) != 0

    def is_taskbar_ignored(self):
        return (self._exStyle & WS_EX_NOACTIVATE) and not (self._exStyle & WS_EX_APPWINDOW)

    def is_minimized(self):
        return (self._winStyle & WS_MINIMIZE) != 0

    def is_maximized(self):
        return (self._winStyle & WS_MAXIMIZE) != 0

class WindowProxy:
    def __init__(self, hwnd):
        self._hwnd = hwnd
        self.initialized = False
        self.ignored = False
        self.valid = True
        self.changed = False
        self.window_info = WindowInfo()
        self.always_top = False

        self._dirty = False
        self._info = WindowInfo()
        
        self._position = winfuncs.w.RECT()

        self._layout_dirty = False
        self._layout_position = Rect()
        self._layout_margin = None
        self._applied_position = Rect()

        self._proxy_hidden = False
        self._proxy_always_top = False

    def _initialize(self):
        self.initialized = True

        self._info.is_child = winfuncs.WindowIsChild(self._hwnd)

        self._update_info()
        self._transfer_info()

    def _cleanup(self):
        if self._proxy_hidden:
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
        if self._proxy_always_top:
            self._apply_always_top(False)

    def __str__(self):
        return f"{{ PROXY {self._info.window_title} | {self._info.window_class} @{self._hwnd} }}"

    def _update_hung(self):
        hung = winfuncs.IsHungAppWindow(self._hwnd)
        if hung != self._info.is_hung:
            self._info.is_hung = hung
            self._dirty = True

    def _update_info(self):
        """ Update winproxy information for this window """
        title = winfuncs.WindowGetTitle(self._hwnd)
        if title != self._info.window_title:
            self._info.window_title = title
            self._dirty = True

        cls = winfuncs.WindowGetClass(self._hwnd)
        if cls != self._info.window_class:
            self._info.window_class = cls
            self._dirty = True

        visible = winfuncs.IsWindowVisible(self._hwnd)
        if visible != self._info.visible:
            self._info.visible = visible
            self._dirty = True

        cloaked = winfuncs.WindowIsCloaked(self._hwnd)
        if cloaked != self._info.cloaked:
            self._info.cloaked = cloaked
            self._dirty = True

        style = winfuncs.WindowGetStyle(self._hwnd)
        if style != self._info._winStyle:
            self._info._winStyle = style
            self._dirty = True

        exStyle = winfuncs.WindowGetExStyle(self._hwnd)
        if exStyle != self._info._exStyle:
            self._info._exStyle = exStyle
            self._dirty = True

        has_rect = winfuncs.GetWindowRect(self._hwnd, winfuncs.c.byref(self._position))
        if has_rect:
            if (self._info.rect.position[0] != self._position.left
                or self._info.rect.position[1] != self._position.top
                or self._info.rect.position[2] != self._position.right
                or self._info.rect.position[3] != self._position.bottom):

                self._info.rect.position = (self._position.left, self._position.top, self._position.right, self._position.bottom)
                self._dirty = True

    def _update_layout(self):
        with WindowProxyLock:
            self._layout_dirty = False
            self._applied_position.assign(self._layout_position)

        try_position = [
            self._applied_position.left,
            self._applied_position.top,
            self._applied_position.width,
            self._applied_position.height,
        ]

        if self._layout_margin is not None:
            # Apply a preset margin to the window
            try_position[0] += self._layout_margin
            try_position[1] += self._layout_margin
            try_position[2] -= self._layout_margin*2
            try_position[3] -= self._layout_margin*2
        else:
            # Find the margin that this window wants from the OS
            adjustedRect = winfuncs.w.RECT()
            adjustedRect.left = try_position[0]
            adjustedRect.top = try_position[1]
            adjustedRect.right = try_position[0] + try_position[2]
            adjustedRect.bottom = try_position[1] + try_position[3]

            winfuncs.AdjustWindowRectEx(
                winfuncs.c.byref(adjustedRect),
                self._info._winStyle,
                False,
                self._info._exStyle,
            )

            try_position[0] = adjustedRect.left + 3
            try_position[1] += 2
            try_position[2] = adjustedRect.right - adjustedRect.left - 6
            try_position[3] = adjustedRect.bottom - try_position[1] - 3

        set_position_allowed = True
        needed_tries = 0
        for tries in range(0, 10):
            zorder = winfuncs.HWND_BOTTOM
            if self._proxy_always_top:
                zorder = winfuncs.HWND_TOPMOST
            set_position_allowed = winfuncs.SetWindowPos(
                self._hwnd,
                zorder,
                try_position[0], try_position[1],
                try_position[2], try_position[3],
                winfuncs.SWP_NOACTIVATE
            )

            if not set_position_allowed:
                break

            has_rect = winfuncs.GetWindowRect(self._hwnd, winfuncs.c.byref(self._position))
            if not has_rect:
                break

            if (try_position[0] != self._position.left
                or try_position[1] != self._position.right
                or try_position[2] != (self._position.right - self._position.left)
                or try_position[3] != (self._position.bottom - self._position.top)
            ):
                # Keep trying!
                continue
            else:
                needed_tries = tries+1
                break

        if not set_position_allowed:
            print(f"Failed to set {try_position} on {self}")

    def _transfer_info(self):
        """ Transfer info from winproxy thread to exposed members. """
        with WindowProxyLock:
            self.window_info.set(self._info)
            self.changed = True
        self._dirty = False

    def _update(self):
        if not self.valid:
            # Never update if we are no longer valid
            return

        if self.ignored:
            # Don't update windows that are permanently ignored
            return

        if not winfuncs.IsWindow(self._hwnd):
            # If the window was closed, we become invalid
            self.valid = False
            return

        # Update whether this is a hung window
        self._update_hung()
        if self._info.is_hung:
            # Don't do anything else while hung
            if self._dirty:
                self._transfer_info()
            return

        # Reposition if the window layout has changed
        if self._layout_dirty:
            self._update_layout()

        # Update actual information about this window
        self._update_info()
        if self._dirty:
            self._transfer_info()

    def set_layout(self, new_position, margin=None):
        with WindowProxyLock:
            self._layout_position.assign(new_position)
            self._layout_margin = margin
            self._layout_dirty = True

    def _zorder_top(self):
        zpos = winfuncs.HWND_TOP
        if self._proxy_always_top:
            zpos = winfuncs.HWND_TOPMOST

        winfuncs.SetWindowPos(self._hwnd, zpos, 0, 0, 0, 0,
                winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE)

    def _zorder_bottom(self):
        if self._proxy_always_top:
            return

        winfuncs.SetWindowPos(self._hwnd, winfuncs.HWND_BOTTOM, 0, 0, 0, 0,
                winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE)

    def _apply_always_top(self, always_top):
        self._proxy_always_top = always_top
        if always_top:
            winfuncs.SetWindowPos(self._hwnd, winfuncs.HWND_TOPMOST, 0, 0, 0, 0,
                    winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE)
        else:
            winfuncs.SetWindowPos(self._hwnd, winfuncs.HWND_NOTOPMOST, 0, 0, 0, 0,
                    winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE)

    def show(self):
        def proxy_show():
            self._proxy_hidden = False
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
            self._zorder_top()
        ProxyCommands.queue(proxy_show)

    def show_with_rect(self, new_rect):
        def proxy_show_rect():
            self._proxy_hidden = False
            zorder = winfuncs.HWND_TOP
            if self._proxy_always_top:
                zorder = winfuncs.HWND_TOPMOST
            winfuncs.SetWindowPos(self._hwnd, zorder,
                new_rect.left, new_rect.top,
                new_rect.width, new_rect.height,
                winfuncs.SWP_NOACTIVATE)
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
        ProxyCommands.queue(proxy_show_rect)

    def hide(self):
        def proxy_hide():
            self._proxy_hidden = True
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_HIDE)
        ProxyCommands.queue(proxy_hide)

    def close(self):
        def proxy_close():
            winfuncs.PostMessageW(self._hwnd, winfuncs.WM_CLOSE, 0, 0)
        ProxyCommands.queue(proxy_close)

    def poke(self):
        def proxy_poke():
            zorder = winfuncs.HWND_BOTTOM
            if self._proxy_always_top:
                zorder = winfuncs.HWND_TOPMOST
            winfuncs.SetWindowPos(self._hwnd, zorder,
                self._info.rect.left-2, self._info.rect.top-2,
                self._info.rect.width+4, self._info.rect.height+4,
                winfuncs.SWP_NOACTIVATE)
            winfuncs.SetWindowPos(self._hwnd, zorder,
                self._info.rect.left, self._info.rect.top,
                self._info.rect.width, self._info.rect.height,
                winfuncs.SWP_NOACTIVATE)
        ProxyCommands.queue(proxy_poke)

    def set_always_on_top(self, always_on_top):
        if self.always_top == always_on_top:
            return
        self.always_top = always_on_top
        ProxyCommands.queue(functools.partial(self._apply_always_top, always_on_top))

    def minimize(self):
        def proxy_minimize():
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_FORCEMINIMIZE)
        ProxyCommands.queue(proxy_minimize)

    def restore(self):
        def proxy_restore():
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_RESTORE)
        ProxyCommands.queue(proxy_restore)

    def remove_maximized(self):
        def proxy_unmaximize():
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
        ProxyCommands.queue(proxy_unmaximize)

    def remove_titlebar(self):
        def proxy_remove_titlebar():
            style = self._info._winStyle
            if style & WS_CAPTION:
                style = style & ~WS_CAPTION
                winfuncs.WindowSetStyle(self._hwnd, style)
        ProxyCommands.queue(proxy_remove_titlebar)