from multiprocessing import Process
from time import sleep
from Queue import Empty

from experiments import AVAILABLE_PROTOCOLS


#### CLASSES ####

class StimulusController(Process):
    """Controls and manages lifetime of stimulus objects."""

    def __init__(self, shared):
        super(StimulusController, self).__init__()

        self.shared = shared
        self.current_process = None

    def run(self):

        # Logic:
        # 1) Run while running
        # 2) Check if new stimulus is requested
        # 3) If not, keep running
        # 4) If yes, kill old process & instantiate/start new one
        # 5) Parameters are passed through generic shared array
        # 6) Stimulus subclasses provide static dictionary of available parameters

        while self.shared.running.value == 1:

            try:
                stimulus_command = self.shared.stimulus_commands.get(block=False)
                signal = stimulus_command["signal"]

                if signal == "terminate":
                    if self.current_process is not None:
                        self.current_process.terminate()
                        self.current_process = None

                elif signal == "start":
                    if self.current_process is not None:
                        self.current_process.terminate()

                    sleep(1.0)

                    project, protocol = stimulus_command["project"], stimulus_command["protocol"]

                    try:
                        stimulus = AVAILABLE_PROTOCOLS[project]["protocols"][protocol]

                        self.current_process = StimulusProcess(stimulus[0], stimulus[1], self.shared)
                        self.current_process.start()
                    except KeyError:
                        print "Stimulus not found"

            except Empty:
                # Keeps stimulus running...
                pass


class StimulusProcess(Process):
    """Container for stimulus objects, as managed by the controller."""

    def __init__(self, StimulusClass, stimulus_param, shared):
        super(StimulusProcess, self).__init__()

        self.shared = shared
        self.stimulus_class = StimulusClass
        self.stimulus_param = stimulus_param
        self.app = None

    def run(self):
        self.app = self.stimulus_class(self.shared, **self.stimulus_param)
        self.app.run()
