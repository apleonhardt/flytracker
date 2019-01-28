from multiprocessing import Process
from time import sleep

from peripheral.framesync import OptogeneticLight


class OptoProcess(Process):
    """Represents the optogenetic light to the main system and accepts light status commands."""

    def __init__(self, shared):
        super(OptoProcess, self).__init__()
        self.shared = shared
        self.ol = None
        self.current_intensity = 0

    def run(self):

        # Note: Devide ID is currently hardcoded but could easily be moved to configuration
        self.ol = OptogeneticLight(device_name="A501M1XR")

        self.current_intensity = self.shared.opto_intensity.value
        self.ol.set_global_intensity(self.current_intensity)

        while self.shared.running.value == 1:
            sleep(0.01)  # to avoid overloading the process with updates

            if self.current_intensity != self.shared.opto_intensity.value:
                self.ol.set_global_intensity(self.shared.opto_intensity.value)
                self.current_intensity = self.shared.opto_intensity.value

                # print "Changed opto intensity to {0}".format(self.current_intensity)

        self.ol.set_global_intensity(0)
        self.ol.close()
