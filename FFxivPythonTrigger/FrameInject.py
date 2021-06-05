from queue import Queue
from threading import Lock
from traceback import format_exc
from typing import List, Tuple
from time import perf_counter
from inspect import getfile, getsourcelines, getframeinfo, stack, Traceback

from .Logger import Logger
from .hook import Hook
from ctypes import *

_logger = Logger("Frame Inject")
MISSION_TIME_LIMIT = 0.05


class FrameInjectHook(Hook):
    _continue_works = dict()
    _once_works = Queue()
    _lock = Lock()

    def register_continue_call(self, call, *args, **kwargs):
        with self._lock:
            self._continue_works[call] = (args, kwargs)

    def unregister_continue_call(self, call):
        try:
            with self._lock:
                del self._continue_works[call]
        except KeyError:
            pass

    def register_once_call(self, call, *args, **kwargs):
        self._once_works.put((call, args, kwargs))

    argtypes = [c_void_p, c_void_p]

    def call(self, call, *args, **kwargs):
        start = perf_counter()
        call(*args, **kwargs)
        use = perf_counter() - start
        if use > MISSION_TIME_LIMIT:
            _logger.warning("frame mission over time {:.2}s (limit:{:.2}s):\n"
                            "at:\t{}:{}".format(use, MISSION_TIME_LIMIT, getfile(call), getsourcelines(call)[1]))

    def hook_function(self, *oargs):
        try:
            while not self._once_works.empty():
                try:
                    call, a, k = self._once_works.get(False)
                    self.call(call, *a, **k)
                except Exception:
                    _logger.error("error in frame call:\n" + format_exc())
            if self._lock.acquire(False):
                for c, v in self._continue_works.items():
                    try:
                        self.call(c, *v[0], **v[1])
                    except Exception:
                        del self._continue_works[c]
                        _logger.error("error in frame call, continue work will be removed:\n" + format_exc())
                self._lock.release()
        except Exception:
            _logger.error("error in frame inject:\n" + format_exc())
        return self.original(*oargs)
