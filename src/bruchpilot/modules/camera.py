from multiprocessing import Process
from time import sleep, clock
from os.path import join
import csv

import numpy as np
import cv2

from peripheral import camera
from modules.helpers import FrameCounter, BackgroundSubtractor


## TODOs:

# Make processes continuously running/non-blocking to avoid hold-up during shutdown or unresponsiveness
# Overhaul logging
# Maybe image arrays need to be LOCKED to circumvent tearing

class CameraManager(object):
    """Represents a camera to the tracking system."""

    def __init__(self, camera_name, camera_settings, shared, debug=False):

        self.camera_name = camera_name
        self.camera_settings = camera_settings
        self.shared = shared
        self.debug = debug

        # Initialize sub-structures:

        self.shared.register_camera(camera_name, camera_settings)

        self.camera_process = CameraProcess(self.camera_name, self.camera_settings, self.shared, debug=self.debug)
        self.recorder_process = RecorderProcess(self.camera_name, self.camera_settings, self.shared, debug=self.debug)
        self.tracker_process = TrackerProcess(self.camera_name, self.camera_settings, self.shared, debug=self.debug)

    def start(self):
        self.camera_process.start()
        self.recorder_process.start()
        self.tracker_process.start()


class CameraProcess(Process):
    """Implements communication between the camera manager and an individual camera."""

    def __init__(self, camera_name, camera_settings, shared, debug=False):

        super(CameraProcess, self).__init__()

        self.debug = debug
        self.camera_name = camera_name
        self.cam = None
        self.camera_settings = camera_settings
        self.shared = shared
        self.counter = FrameCounter("Camera {0}".format(self.camera_settings["serial"]), every=1.0)

    def set_up(self):

        camera_serial = self.camera_settings["serial"]

        self.cam = camera.PGCamera(serial_number=camera_serial)
        self.cam.connect()

        self.cam.set_property_values(self.camera_settings)
        self.cam.set_format_configuration(**self.camera_settings["f7"])
        self.cam.set_trigger(True)

        self.cam.start_capture()

        if self.debug:
            print self.cam.get_camera_info()

    def tear_down(self):
        self.cam.disconnect()

    def run(self):

        # For some reason, this has to happen AFTER the object
        # is pickled/moved to other process! Camera object doesn't
        # appear to survive transition...
        self.set_up()

        frame_idx = 0

        while self.shared.running.value == 1:
            image = self.cam.grab()
            arr, ts = np.array(image), image.get_timestamp()

            # It's unclear whether this is just system clock or something else: CHECK!
            stamp = ts["seconds"] + ts["microSeconds"] / 1000000.0

            if self.shared.recording.value == 1:
                frame_idx += 1

            msg = {
                "frame_index": frame_idx,
                "image": arr,
                "camera_timestamp": stamp,
                "process_timestamp": clock(),
            }

            # Put in shared
            memoryview(self.shared.images_raw[self.camera_name])[:] = arr.reshape((-1))

            self.shared.images_q[self.camera_name].put(msg)
            self.shared.images_q_tracker[self.camera_name].put(msg)

            self.counter.step(mute=not self.debug)
            self.shared.fps_camera[self.camera_name].value = self.counter.get_frequency()

        self.tear_down()


class RecorderProcess(Process):
    """Stores camera frames in a video file."""

    def __init__(self, camera_name, camera_settings, shared, debug=False):

        super(RecorderProcess, self).__init__()

        self.camera_name = camera_name
        self.camera_settings = camera_settings
        self.debug = debug
        self.shared = shared

        self.counter = FrameCounter("Recorder {0}".format(self.camera_settings["serial"]), every=1.0)

    def run(self):

        # Video stream:

        framesize = (self.camera_settings["f7"]["width"], self.camera_settings["f7"]["height"])
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        save_path = join(self.shared.data_folder, "raw", "{0}.avi".format(self.camera_name))
        writer = cv2.VideoWriter(save_path, fourcc=fourcc, fps=self.shared.framerate.value,
                                 frameSize=framesize,
                                 isColor=False)

        # Metadata stream:

        save_path = join(self.shared.data_folder, "raw", "{0}.csv".format(self.camera_name))
        metadata_file = open(save_path, mode="wb")
        metadata_stream = csv.writer(metadata_file)
        metadata_stream.writerow(["frame_number", "process_timestamp", "camera_timestamp"])

        while self.shared.running.value == 1:
            msg = self.shared.images_q[self.camera_name].get(block=True)
            frame = msg["image"].astype("uint8")

            if self.shared.recording.value == 1:
                if self.shared.recording_raw.value == 1:
                    writer.write(frame)
                    metadata_stream.writerow([msg["frame_index"], msg["process_timestamp"], msg["camera_timestamp"]])

            self.counter.step(mute=not self.debug)
            self.shared.fps_recorder[self.camera_name].value = self.counter.get_frequency()

        writer.release()
        metadata_file.close()


class TrackerProcess(Process):
    """Implements background subtraction and object identification."""

    def __init__(self, camera_name, camera_settings, shared, debug=False):

        super(TrackerProcess, self).__init__()

        self.camera_name = camera_name
        self.camera_settings = camera_settings
        self.debug = debug
        self.shared = shared

        self.counter = FrameCounter("Tracker {0}".format(self.camera_settings["serial"]), every=1.0)

    def run(self):

        alpha = self.shared.gsettings["background_subtraction_alpha"]
        th = self.shared.gsettings["background_subtraction_threshold"]
        background_model = BackgroundSubtractor(alpha, th)

        target_buffer = self.shared.targets[self.camera_name]
        empty_array = np.zeros_like(target_buffer) * 0

        save_path = join(self.shared.data_folder, "tracking", "{0}.csv".format(self.camera_name))
        metadata_file = open(save_path, mode="wb")
        metadata_stream = csv.writer(metadata_file)
        metadata_stream.writerow(
            ["frame_number", "process_timestamp", "camera_timestamp", "x", "y", "area", "opto_intensity"])

        while self.shared.running.value == 1:

            msg = self.shared.images_q_tracker[self.camera_name].get(block=True)
            image = msg["image"]

            mask = background_model.apply(image)
            _, contours, hierarchy = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            self.shared.targets_number[self.camera_name].value = len(contours)

            # Clear out previous targets
            memoryview(target_buffer)[:] = empty_array

            for idx, cnt in enumerate(contours):

                m = cv2.moments(cnt)

                if m['m00'] > 0.0:

                    cx = int(m['m10'] / m['m00'])
                    cy = int(m['m01'] / m['m00'])

                    # Filter by various moments:

                    # Write target out:
                    if self.shared.recording.value == 1:
                        metadata_stream.writerow([msg["frame_index"], msg["process_timestamp"], msg["camera_timestamp"],
                                                  cx, cy, m['m00'], self.shared.opto_intensity.value])

                    # Store for GUI:
                    if idx < len(target_buffer) / 2:
                        target_buffer[2 * idx] = cx
                        target_buffer[2 * idx + 1] = cy

            memoryview(self.shared.images_raw_tracker[self.camera_name])[:] = mask.reshape((-1))

            self.counter.step(mute=not self.debug)
            self.shared.fps_tracker[self.camera_name].value = self.counter.get_frequency()
