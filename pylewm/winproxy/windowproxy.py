import pylewm.winproxy.winfuncs as winfuncs
from pylewm.commands import CommandQueue, Commands
from pylewm.rects import Rect
import pylewm.config

from threading import Lock
import functools
import time
import math

WindowProxyLock = Lock()
WindowsByHandle : dict[int, 'WindowProxy'] = dict()
ProxyCommands = CommandQueue()

class WindowInfo:
    BORDER_STYLES = winfuncs.WS_SYSMENU | winfuncs.WS_DLGFRAME | winfuncs.WS_BORDER | winfuncs.WS_POPUP | winfuncs.WS_CAPTION

    def __init__(self):
        self.window_title = ""
        self.window_class = ""
        self.visible = False
        self.cloaked = False
        self.is_child = False
        self.is_hung = False
        self.is_resizable = False
        self.is_force_visible = False
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
        self.is_force_visible = other.is_force_visible
        self.is_resizable = other.is_resizable
        self.rect.assign(other.rect)
        self._winStyle = other._winStyle
        self._exStyle = other._exStyle

    def can_resize(self):
        return (self._winStyle & winfuncs.WS_SIZEBOX) != 0

    def is_taskbar_ignored(self):
        return (self._exStyle & winfuncs.WS_EX_NOACTIVATE) and not (self._exStyle & winfuncs.WS_EX_APPWINDOW)

    def is_minimized(self):
        return (self._winStyle & winfuncs.WS_MINIMIZE) != 0

    def is_maximized(self):
        return (self._winStyle & winfuncs.WS_MAXIMIZE) != 0

    def get_border_styles(self):
        return (self._winStyle & WindowInfo.BORDER_STYLES)

class WindowProxy:
    ProgramStartTime = time.time()
    UpdateFrameCounter = 0
    UpdateStartTime = 0

    def __init__(self, hwnd):
        self._hwnd = hwnd
        self.initialized = False
        self.permanent_ignore = False
        self.temporary_ignore = False
        self.want_removed_titlebar = False
        self.valid = True
        self.changed = False
        self.window_info = WindowInfo()
        self.always_top = False
        self.has_tab_group = False
        self.interval_hash = hash(id(self))
        self.update_interval = 0
        self.creation_time = time.time()

        self._dirty = False
        self._info = WindowInfo()
        
        self._position = winfuncs.w.RECT()

        self._layout_dirty = False
        self._layout_position = Rect()
        self._layout_edges_flush = None
        self._layout_applied = False
        self._has_layout_position = None
        self._proxy_has_tab_group = False
        self._applied_position = Rect()

        self._proxy_hidden = False
        self._proxy_always_top = False
        self._proxy_resizable = False
        self._proxy_removed_titlebar = False

        self._has_floating_target = False
        self._floating_target = Rect()
        self._applied_floating_target = Rect()

    def _initialize(self):
        self.initialized = True
        self.initialized_time = time.time()

        self._info.is_child = winfuncs.WindowIsChild(self._hwnd)
        self._update_info()
        self._info.is_resizable = (self._info._winStyle & winfuncs.WS_SIZEBOX) != 0
        self._proxy_resizable = self._info.is_resizable

        self._transfer_info()

    def _cleanup(self):
        if self._proxy_hidden:
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
        if self._proxy_always_top:
            self._apply_always_top(False)
        if self._proxy_resizable != self.window_info.is_resizable:
            self._proxy_set_resizable(self.window_info.is_resizable)

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

        visible = winfuncs.IsWindowVisible(self._hwnd)

        # If this is likely to be a relevant window, and we've just created it, pretend it's visible
        # for the first 0.5s. This increases responsiveness when starting new windows, because it can
        # often take a short time before the window becomse visible.
        if (not visible
                and (WindowProxy.UpdateStartTime - self.creation_time) < 0.5
                and self.is_likely_interactable()
                and (WindowProxy.UpdateStartTime - WindowProxy.ProgramStartTime) > 1.0):
            visible = True
            self._info.is_force_visible = True
        else:
            self._info.is_force_visible = False

        if visible != self._info.visible:
            self._info.visible = visible
            self._dirty = True

    def is_likely_interactable(self):
        if self._info.is_child:
            return False
        if (self._info._exStyle & winfuncs.WS_EX_LAYERED) != 0:
            return False
        if (self._info._winStyle & winfuncs.WS_DISABLED) != 0:
            return False
        if (self._info._winStyle & winfuncs.WS_POPUP) != 0:
            return False
        if self._info.window_class not in pylewm.config.WHITELIST_INTERACTIBLE_CLASSES:
            return False
        return True

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

        apply_os_borders = True
        if self._layout_margin:
            margin_size = self._layout_margin[1]
            apply_os_borders = self._layout_margin[0]

            if isinstance(margin_size, int):
                # Apply a preset margin to the window
                try_position[0] += margin_size
                try_position[1] += margin_size
                try_position[2] -= margin_size
                try_position[3] -= margin_size
            elif margin_size:
                # Apply a preset margin to the window
                try_position[0] += margin_size[0]
                try_position[1] += margin_size[1]
                try_position[2] -= margin_size[0]+margin_size[2]
                try_position[3] -= margin_size[1]+margin_size[3]

        if apply_os_borders:
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

            border_left = adjustedRect.left - try_position[0]
            border_right = (try_position[0] + try_position[2]) - adjustedRect.right
            border_bottom = (try_position[1] + try_position[3]) - adjustedRect.bottom
            border_top = 0

            if self.has_tab_group:
                border_top += 30

            if not (self._info._winStyle & winfuncs.WS_SYSMENU):
                border_left += 7
                border_right += 7
                border_bottom += 7

            # Apply the inner border for any edges that aren't flush
            if not self._layout_edges_flush or not self._layout_edges_flush[0]:
                if isinstance(pylewm.config.TilingInnerMargin, int):
                    border_left += math.ceil(pylewm.config.TilingInnerMargin / 2)
                else:
                    border_left += math.ceil(pylewm.config.TilingInnerMargin[0] / 2)
            else:
                if isinstance(pylewm.config.TilingOuterMargin, int):
                    border_left += pylewm.config.TilingOuterMargin
                else:
                    border_left += pylewm.config.TilingOuterMargin[0]

            if not self._layout_edges_flush or not self._layout_edges_flush[1]:
                if isinstance(pylewm.config.TilingInnerMargin, int):
                    border_top += math.ceil(pylewm.config.TilingInnerMargin / 2)
                else:
                    border_top += math.ceil(pylewm.config.TilingInnerMargin[1] / 2)
            else:
                if isinstance(pylewm.config.TilingOuterMargin, int):
                    border_top += pylewm.config.TilingOuterMargin
                else:
                    border_top += pylewm.config.TilingOuterMargin[1]

            if not self._layout_edges_flush or not self._layout_edges_flush[2]:
                if isinstance(pylewm.config.TilingInnerMargin, int):
                    border_right += math.ceil(pylewm.config.TilingInnerMargin / 2)
                else:
                    border_right += math.ceil(pylewm.config.TilingInnerMargin[2] / 2)
            else:
                if isinstance(pylewm.config.TilingOuterMargin, int):
                    border_right += pylewm.config.TilingOuterMargin
                else:
                    border_right += pylewm.config.TilingOuterMargin[2]

            if not self._layout_edges_flush or not self._layout_edges_flush[3]:
                if isinstance(pylewm.config.TilingInnerMargin, int):
                    border_bottom += math.ceil(pylewm.config.TilingInnerMargin / 2)
                else:
                    border_bottom += math.ceil(pylewm.config.TilingInnerMargin[3] / 2)
            else:
                if isinstance(pylewm.config.TilingOuterMargin, int):
                    border_bottom += pylewm.config.TilingOuterMargin
                else:
                    border_bottom += pylewm.config.TilingOuterMargin[3]

            try_position[0] += border_left+1
            try_position[1] += border_top
            try_position[2] -= border_left+border_right+2
            try_position[3] -= border_top+border_bottom+1

        zorder = winfuncs.HWND_BOTTOM
        if self._proxy_always_top:
            zorder = winfuncs.HWND_TOPMOST
        set_position_allowed = winfuncs.SetWindowPos(
            self._hwnd,
            zorder,
            try_position[0], try_position[1],
            try_position[2], try_position[3],
            winfuncs.SWP_NOACTIVATE | winfuncs.SWP_ASYNCWINDOWPOS
        )

        if not set_position_allowed:
            print(f"{time.time()} Failed to set {try_position} on {self}")

    def _update_floating(self):
        with WindowProxyLock:
            self._has_floating_target = False
            self._applied_floating_target.assign(self._floating_target)

        try_position = [
            self._applied_floating_target.left,
            self._applied_floating_target.top,
            self._applied_floating_target.width,
            self._applied_floating_target.height,
        ]

        set_position_allowed = winfuncs.SetWindowPos(
            self._hwnd,
            winfuncs.HWND_TOPMOST,
            try_position[0], try_position[1],
            try_position[2], try_position[3],
            winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOOWNERZORDER
        )
        if not set_position_allowed:
            print(f"Failed to set {try_position} on {self}")

    def _transfer_info(self):
        """ Transfer info from winproxy thread to exposed members. """
        with WindowProxyLock:
            self.window_info.set(self._info)
            self.changed = True
        self._dirty = False

    def _update(self):
        if self.permanent_ignore:
            # Don't update windows that are permanently ignored
            return

        if not self.valid:
            # Never update if we are no longer valid
            return

        # Temporarily ignored windows update at a slower rate to save performance
        if (self.temporary_ignore or self._proxy_hidden) and self.initialized_time < WindowProxy.UpdateStartTime - 1.0:
            self.update_interval = min(self.update_interval + 1, 20)
            if (WindowProxy.UpdateFrameCounter % self.update_interval) != (self.interval_hash % self.update_interval):
                return
        else:
            self.update_interval = 0

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

        # Reposition floating window if it wants to be moved
        if self._has_floating_target:
            self._update_floating()

        if self.want_removed_titlebar:
            self._proxy_update_remove_titlebar()

        # Update actual information about this window
        self._update_info()
        if self._dirty:
            self._transfer_info()

    def set_layout(self, new_position, margin=None, edges_flush=None):
        with WindowProxyLock:
            self._layout_position.assign(new_position)
            self._layout_edges_flush = edges_flush
            self._has_layout_position = True
            self._layout_margin = margin
            self._layout_dirty = True
        
    def restore_layout(self):
        with WindowProxyLock:
            if self._has_layout_position:
                self._layout_dirty = True

    def move_floating_to(self, new_position):
        with WindowProxyLock:
            self._floating_target.assign(new_position)
            self._has_floating_target = True

    def _zorder_top(self):
        zpos = winfuncs.HWND_TOP
        if self._proxy_always_top:
            zpos = winfuncs.HWND_TOPMOST

        winfuncs.SetWindowPos(self._hwnd, zpos, 0, 0, 0, 0,
                winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE | winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOREDRAW)

    def _zorder_bottom(self):
        if self._proxy_always_top:
            return

        winfuncs.SetWindowPos(self._hwnd, winfuncs.HWND_BOTTOM, 0, 0, 0, 0,
                winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE | winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOREDRAW)

    def _apply_always_top(self, always_top):
        self._proxy_always_top = always_top
        if always_top:
            winfuncs.SetWindowPos(self._hwnd, winfuncs.HWND_TOPMOST, 0, 0, 0, 0,
                    winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE | winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOREDRAW)
        else:
            winfuncs.SetWindowPos(self._hwnd, winfuncs.HWND_NOTOPMOST, 0, 0, 0, 0,
                    winfuncs.SWP_NOACTIVATE | winfuncs.SWP_NOMOVE | winfuncs.SWP_NOSIZE | winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOREDRAW)

    def show(self):
        def proxy_show():
            self._proxy_hidden = False
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
            self._zorder_top()
        ProxyCommands.queue(proxy_show)

    def delayed_show(self, delay=0.05):
        def proxy_show():
            self._proxy_hidden = False
        ProxyCommands.queue(proxy_show)
        def delay_show():
            if not self._proxy_hidden:
                winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
                self._zorder_top()
        ProxyCommands.delay(delay, delay_show)

    def show_with_rect(self, new_rect):
        def proxy_show_rect():
            self._proxy_hidden = False
            zorder = winfuncs.HWND_TOP
            if self._proxy_always_top:
                zorder = winfuncs.HWND_TOPMOST
            winfuncs.SetWindowPos(self._hwnd, zorder,
                new_rect.left, new_rect.top,
                new_rect.width, new_rect.height,
                winfuncs.SWP_NOACTIVATE | winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOREDRAW)
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_SHOWNOACTIVATE)
        ProxyCommands.queue(proxy_show_rect)

    def hide(self):
        def proxy_hide():
            self._proxy_hidden = True
            winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_HIDE)
        ProxyCommands.queue(proxy_hide)

    def delayed_hide(self, delay=0.05):
        def proxy_hide():
            self._proxy_hidden = True
        ProxyCommands.queue(proxy_hide)
        def delay_hide():
            if self._proxy_hidden:
                winfuncs.ShowWindowAsync(self._hwnd, winfuncs.SW_HIDE)
        ProxyCommands.delay(delay, delay_hide)

    def hide_permanent(self):
        def proxy_hide():
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
                winfuncs.SWP_NOACTIVATE | winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOREDRAW)
            winfuncs.SetWindowPos(self._hwnd, zorder,
                self._info.rect.left, self._info.rect.top,
                self._info.rect.width, self._info.rect.height,
                winfuncs.SWP_NOACTIVATE | winfuncs.SWP_ASYNCWINDOWPOS | winfuncs.SWP_NOREDRAW)
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
        self.want_removed_titlebar = True

    def _proxy_update_remove_titlebar(self):
        if self.want_removed_titlebar and not self._proxy_removed_titlebar and not self._info.is_force_visible:
            self._proxy_removed_titlebar = True
            style = self._info._winStyle
            if style & winfuncs.WS_CAPTION:
                style = style & ~winfuncs.WS_CAPTION
                winfuncs.WindowSetStyle(self._hwnd, style)

    def set_resizable(self, resizable:bool):
        ProxyCommands.queue(lambda: self._proxy_set_resizable(resizable))

    def _proxy_set_resizable(self, resizable:bool):
        self._proxy_resizable = resizable
        style = self._info._winStyle
        if style & winfuncs.WS_SIZEBOX:
            if not resizable:
                style = style & ~winfuncs.WS_SIZEBOX
                winfuncs.WindowSetStyle(self._hwnd, style)
        else:
            if resizable:
                style = style | winfuncs.WS_SIZEBOX
                winfuncs.WindowSetStyle(self._hwnd, style)