from os import path, makedirs
from datetime import datetime
from shutil import copy2

from yaml import load_all
from git import Repo

from modules.camera import CameraManager
from modules.trigger import TriggerProcess
from modules.opto import OptoProcess
from modules.shared import Shared
from modules.gui import GuiProcess
from modules.stimulus import StimulusController


class BruchpilotApplication(object):
    """Main class that delegates all sub-components of the control system."""

    def __init__(self, configuration_file):

        # Load settings:
        self.general_settings, self.camera_settings = list(load_all(open(configuration_file)))

        # Check current git hash to be able to trace back which version was used:
        repository = Repo(__file__, search_parent_directories=True)
        self.general_settings["git_hash"] = repository.head.object.hexsha

        # Activate all modules:
        self.shared = Shared(self.general_settings, self.camera_settings)
        self.trigger = TriggerProcess(self.shared)
        self.opto = OptoProcess(self.shared)
        self.cps = [CameraManager(my_key, self.camera_settings[my_key], self.shared, debug=False) for my_key in
                    self.camera_settings.keys()]
        self.gui = GuiProcess(self.shared)
        self.stimulus = StimulusController(self.shared)

        # Set up data folder:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        folder_name = path.join(self.general_settings["data_folder"], stamp)

        makedirs(path.join(folder_name, "raw"))
        makedirs(path.join(folder_name, "snapshot"))
        makedirs(path.join(folder_name, "tracking"))

        self.shared.data_folder = folder_name

        # Copy calibration settings etc.:
        copy2(self.general_settings["current_calibration"], folder_name)
        copy2(configuration_file, folder_name)

    def start(self):
        """Initiates boot process."""

        self.gui.start()
        self.trigger.start()
        self.opto.start()
        self.stimulus.start()

        for cp in self.cps:
            cp.start()
