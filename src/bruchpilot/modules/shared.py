from multiprocessing import Queue, Value, Array
import ctypes

TARGET_STORAGE_N = 20  # defines the maximum number of trackable targets


class Shared(object):
    """# This defines the big message container. It resembles ROS without the tooling or niceties,
    but is cross-platform and implemented in pure Python."""

    def __init__(self, gsettings, csettings):
        self.gsettings = gsettings
        self.csettings = csettings
        self.camera_names = csettings.keys()

        self.data_folder = None

        # State flags
        self.running = Value('b', 1)
        self.recording = Value('b', 0)
        self.recording_raw = Value('b', 1)

        # General settings:
        self.framerate = Value('f', gsettings["framerate"])
        self.opto_intensity = Value('i', 0)

        # Camera containers:
        self.images_raw = dict()
        self.images_raw_tracker = dict()
        self.images_q = dict()
        self.images_q_tracker = dict()

        self.targets = dict()
        self.targets_number = dict()

        self.fps_camera = dict()
        self.fps_recorder = dict()
        self.fps_tracker = dict()

        # Stimulus things:

        self.stimulus_commands = Queue()

    def register_camera(self, cname, camera_settings):
        frame_size = (camera_settings["f7"]["width"], camera_settings["f7"]["height"])

        self.images_raw[cname] = Array(ctypes.c_uint8, frame_size[0] * frame_size[1], lock=False)
        self.images_raw_tracker[cname] = Array(ctypes.c_uint8, frame_size[0] * frame_size[1], lock=False)

        self.images_q[cname] = Queue()
        self.images_q_tracker[cname] = Queue()

        self.targets[cname] = Array(ctypes.c_uint16, TARGET_STORAGE_N * 2, lock=False)
        self.targets_number[cname] = Value('i', 0)

        self.fps_camera[cname] = Value('f', 0.0)
        self.fps_recorder[cname] = Value('f', 0.0)
        self.fps_tracker[cname] = Value('f', 0.0)
