from functools import partial
from concurrent.futures import ThreadPoolExecutor

import traceback
import threading
import math
import time

InitFunctions = []
stopped = False

class CommandQueue:
    def __init__(self):
        self.queuedFunctions = []
        self.delayedFunctions = []
        self.queue_lock = threading.RLock()
        self.queue_event = threading.Event()
        self.stopped = False

    def queue(self, fun):
        with self.queue_lock:
            self.queuedFunctions.append(fun)
            self.queue_event.set()

    def delay(self, delay, fun):
        with self.queue_lock:
            self.delayedFunctions.append([time.monotonic() + delay, fun])
            self.queue_event.set()

    def run_with_update(self, updatefunc):
        global stopped
        while not stopped:
            try:
                updatefunc()
            except Exception as ex:
                traceback.print_exc()
            self.process(self.suggested_timeout())
        
    def process(self, timeout):
        global stopped
        if stopped:
            return
        self.queue_event.wait(timeout)
        if stopped:
            return

        now_time = time.monotonic()

        run = None
        with self.queue_lock:
            run = list(self.queuedFunctions)

            new_delayed = []
            for delayed in self.delayedFunctions:
                if delayed[0] <= now_time:
                    run.append(delayed[1])
                else:
                    new_delayed.append(delayed)
            self.delayedFunctions = new_delayed

            self.queuedFunctions = []
            self.queue_event.clear()

        try:
            for cmd in run:
                run_pyle_command(cmd)
        except Exception as ex:
            traceback.print_exc()

    def suggested_timeout(self):
        delay = 1.0 / 60.0
        now_time = time.monotonic()

        with self.queue_lock:
            for delayed in self.delayedFunctions:
                delay = min(delay, delayed[0] - now_time)
        return max(delay, 0.0)

Commands = CommandQueue()
AsyncCommandThreadPool = ThreadPoolExecutor(max_workers=64)

def delay_pyle_command(delay, fun):
    Commands.delay(delay, fun)

def queue_pyle_command(fun):
    Commands.queue(fun)

class PyleCommand:
    @staticmethod
    def Threaded(func):
        cmd = PyleCommand(func)
        cmd.threaded = True
        return cmd
    
    def __init__(self, func):
        self.func = func
        self.threaded = False

    def __call__(self, *args, **kwargs):
        cmd = PyleCommand(
            partial(self.func, *args, **kwargs)
        )
        cmd.threaded = self.threaded
        return cmd

    def execute_on_thread(self):
        try:
            self.func()
        except Exception as ex:
            traceback.print_exc()

    def run(self):
        if self.threaded:
            AsyncCommandThreadPool.submit(self.execute_on_thread)
        else:
            self.func()

def run_pyle_command(fun):
    if isinstance(fun, PyleCommand):
        fun.run()
    else:
        fun()

def PyleInit(fun):
    InitFunctions.append(fun)
    return fun
