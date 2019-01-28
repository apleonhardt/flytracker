import time

import numpy as np
import cv2


class FrameCounter(object):
    """Helper class for implementing a simple FPS timer."""

    def __init__(self, name, every=1.0):
        """"""
        self.every = every
        self.name = name
        self.last = time.clock()
        self.counter = 0
        self.last_fps = 0.0

    def step(self, mute=False):
        self.counter += 1
        current = time.clock()
        passed = current - self.last

        if passed >= self.every:
            fps = self.counter / float(passed)
            self.last = time.clock()
            self.counter = 0
            self.last_fps = fps
            if not mute:
                print "[{0}] Running at {1:.2f}Hz".format(self.name, self.last_fps)

    def get_frequency(self):
        return self.last_fps


class BackgroundSubtractor(object):
    """Implementation of a simple low-pass-based background subtraction."""

    def __init__(self, alpha, k):

        self.alpha = alpha
        self.k = k
        self.initialized = False

        self._mean = None
        self._mask = None
        self._rect = None

    def apply(self, frame):

        if not self.initialized:

            self._mean = np.zeros_like(frame, dtype="float64") + frame
            self._mask = np.zeros_like(frame, dtype="uint8")
            self._rect = np.zeros_like(frame, dtype="uint8")

            self.initialized = True

        else:

            cv2.accumulateWeighted(frame, self._mean, self.alpha)

            # This call implicitly rectifies!
            # Only works for dark targets on dark ground
            cv2.subtract(self._mean.astype("uint8"), frame, self._rect)

            cv2.threshold(self._rect, self.k, 255, cv2.THRESH_BINARY, self._mask)

        return self._mask
