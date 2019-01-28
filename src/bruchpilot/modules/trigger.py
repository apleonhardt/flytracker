from multiprocessing import Process
from time import sleep

from peripheral.framesync import FrameSync


class TriggerProcess(Process):
    """Simple controller for camera trigger."""

    def __init__(self, shared):
        super(TriggerProcess, self).__init__()
        self.shared = shared

    def run(self):

        self.fs = FrameSync()
        self.current_framerate = self.shared.framerate.value

        self.fs.set_framerate(self.current_framerate, duty_cycle=0.5)
        self.fs.start()

        while self.shared.running.value == 1:
            sleep(1.0)

            if self.current_framerate != self.shared.framerate.value:
                self.fs.set_framerate(self.shared.framerate.value, duty_cycle=0.5)
                self.current_framerate = self.shared.framerate.value

                print "Changed framerate to {0}Hz".format(self.current_framerate)

        self.fs.stop()
        self.fs.close()