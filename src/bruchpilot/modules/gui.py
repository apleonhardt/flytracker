from multiprocessing import Process
from os.path import join
import traceback
from datetime import datetime

import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore, uic
import pyqtgraph as qtg
from PIL import Image, ImageQt
import cv2
import yaml

from experiments import AVAILABLE_PROTOCOLS


# TODOs:
#
# Move snapshot routine to thread
# Clean up plotting code

class GuiProcess(Process):
    def __init__(self, shared):
        super(GuiProcess, self).__init__()
        self.shared = shared

    def run(self):
        app = QtWidgets.QApplication([])
        win = BruchpilotGui(self.shared)
        app.exec_()


class BruchpilotGui(QtWidgets.QMainWindow):
    def __init__(self, shared):
        super(BruchpilotGui, self).__init__()
        self.shared = shared
        self.current_camera = None

        self.snapshot_idx = 0

        n_cameras = len(self.shared.camera_names)
        self.fps_camera_array = np.zeros(shape=(n_cameras, 30))
        self.fps_recorder_array = np.zeros(shape=(n_cameras, 30))
        self.fps_tracker_array = np.zeros(shape=(n_cameras, 30))
        self.num_tracker_array = np.zeros(shape=(n_cameras, 30))
        self.fps_xaxis = np.linspace(-30, 0, num=30)

        self.init_ui()

    def init_ui(self):
        qtg.setConfigOptions(foreground="#000000", background="#FFFFFF")
        uic.loadUi("bruchpilot.ui", self)

        self.button_record.toggled[bool].connect(self.toggle_recording)
        self.button_snapshot.clicked.connect(self.take_snapshot)
        self.button_snapshot_repeat.toggled[bool].connect(self.toggle_snapshot_repeat)
        # self.button_writemetadata.clicked.connect(self.write_metadata)
        # self.button_set_protocol.clicked.connect(self.set_protocol)

        self.check_recordraw.toggled[bool].connect(self.toggle_recordingraw)
        self.check_recordraw.setChecked(bool(self.shared.recording_raw.value))

        # self.button_record.setEnabled(False)

        # Selection for camera view:
        self.camselector.clear()
        self.camselector.addItems(self.shared.camera_names)
        self.camselector.activated[str].connect(self.change_camera_view)
        self.current_camera = self.shared.camera_names[0]

        # Selection for projects:
        self.selector_project.clear()
        self.selector_project.addItems(self.shared.gsettings["available_projects"])

        # Selection for protocols:
        self.selector_protocol_set.clear()
        self.selector_protocol_set.addItems([""] + AVAILABLE_PROTOCOLS.keys())
        self.selector_protocol_set.activated[str].connect(self.change_protocol_set)

        # PyQtGraph set-up:
        self.plot_fps_camera.setLabels(left="Rate (Hz)", bottom="Time (s)")
        self.plot_fps_camera.hideButtons()
        self.plot_fps_camera.setRange(yRange=(0, 120), xRange=(-30, 0))
        self.plot_fps_camera.disableAutoRange()
        self.plot_fps_camera.setMouseEnabled(x=False, y=False)

        self.plot_fps_recorder.setLabels(left="Rate (Hz)", bottom="Time (s)")
        self.plot_fps_recorder.hideButtons()
        self.plot_fps_recorder.setRange(yRange=(0, 120), xRange=(-30, 0))
        self.plot_fps_recorder.disableAutoRange()
        self.plot_fps_recorder.setMouseEnabled(x=False, y=False)

        self.plot_fps_tracker.setLabels(left="Rate (Hz)", bottom="Time (s)")
        self.plot_fps_tracker.hideButtons()
        self.plot_fps_tracker.setRange(yRange=(0, 120), xRange=(-30, 0))
        self.plot_fps_tracker.disableAutoRange()
        self.plot_fps_tracker.setMouseEnabled(x=False, y=False)

        self.plot_num_targets.setLabels(left="Number", bottom="Time (s)")
        self.plot_num_targets.hideButtons()
        self.plot_num_targets.setRange(yRange=(0, 10), xRange=(-30, 0))
        self.plot_num_targets.disableAutoRange()
        self.plot_num_targets.setMouseEnabled(x=False, y=False)

        self.curves_camera = dict()
        self.curves_recorder = dict()
        self.curves_tracker = dict()
        self.curves_num_targets = dict()

        for cidx, cam in enumerate(self.shared.camera_names):
            pen = qtg.mkPen(width=2, color=qtg.intColor(cidx))
            self.curves_camera[cam] = self.plot_fps_camera.plot(pen=pen)
            self.curves_recorder[cam] = self.plot_fps_recorder.plot(pen=pen)
            self.curves_tracker[cam] = self.plot_fps_tracker.plot(pen=pen)
            self.curves_num_targets[cam] = self.plot_num_targets.plot(pen=pen)

        # Update camera view:
        self.camera_timer = QtCore.QTimer()
        self.camera_timer.timeout.connect(self.update_camera_view)
        self.camera_timer.start(30)

        self.fps_timer = QtCore.QTimer()
        self.fps_timer.timeout.connect(self.update_fps_view)
        self.fps_timer.start(1000)

        self.snapshot_timer = QtCore.QTimer()
        self.snapshot_timer.timeout.connect(self.take_snapshot)

        self.setFixedSize(self.size())
        self.show()

    def update_fps_view(self):
        self.fps_camera_array[:, :-1] = self.fps_camera_array[:, 1:]
        self.fps_recorder_array[:, :-1] = self.fps_recorder_array[:, 1:]
        self.fps_tracker_array[:, :-1] = self.fps_tracker_array[:, 1:]
        self.num_tracker_array[:, :-1] = self.num_tracker_array[:, 1:]

        for cidx, cam in enumerate(self.shared.camera_names):
            # Update:
            self.fps_camera_array[cidx, -1] = self.shared.fps_camera[cam].value
            self.fps_recorder_array[cidx, -1] = self.shared.fps_recorder[cam].value
            self.fps_tracker_array[cidx, -1] = self.shared.fps_tracker[cam].value
            self.num_tracker_array[cidx, -1] = self.shared.targets_number[cam].value

            self.curves_camera[cam].setData(self.fps_xaxis, self.fps_camera_array[cidx, :])
            self.curves_recorder[cam].setData(self.fps_xaxis, self.fps_recorder_array[cidx, :])
            self.curves_tracker[cam].setData(self.fps_xaxis, self.fps_tracker_array[cidx, :])
            self.curves_num_targets[cam].setData(self.fps_xaxis, self.num_tracker_array[cidx, :])

    def get_image_from_camera(self, buffer, camname):
        csettings = self.shared.csettings[camname]
        frame_size = (csettings["f7"]["width"], csettings["f7"]["height"])

        current_image = np.reshape(np.frombuffer(buffer[camname], dtype="uint8"),
                                   frame_size[::-1])
        return current_image

    def update_camera_view(self):

        current_buffer = self.shared.images_raw_tracker if self.check_showforeground.isChecked() else self.shared.images_raw
        image = self.get_image_from_camera(current_buffer, self.current_camera)
        image_c = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        # Processing steps
        if self.check_showtargets.isChecked():
            target_buffer = np.frombuffer(self.shared.targets[self.current_camera], dtype="uint16").reshape((-1, 2))
            for idx in range(target_buffer.shape[0]):
                pt = target_buffer[idx, :].squeeze()
                if np.any(pt):
                    cv2.circle(image_c, (pt[0], pt[1]), 10, (0, 0, 255), 2)

        qim = ImageQt.ImageQt(Image.fromarray(cv2.cvtColor(image_c, cv2.COLOR_BGR2RGB)))
        pixmap = QtGui.QPixmap.fromImage(qim).scaled(self.camview.size())

        self.camview.setPixmap(pixmap)
        self.camview.show()

    def change_camera_view(self, camname):
        self.current_camera = camname

    def toggle_recording(self, checked):

        if checked:

            # Initiate startup sequence:
            selected_set, selected_protocol = self.selector_protocol_set.currentText(), self.selector_protocol.currentText()

            self.shared.stimulus_commands.put({
                "signal": "start",
                "project": selected_set,
                "protocol": selected_protocol,
            })

            self.shared.recording.value = 1
            self.write_metadata()

        else:

            self.shared.recording.value = 0
            self.shared.stimulus_commands.put({"signal": "terminate"})

    def toggle_recordingraw(self, checked):
        if checked:
            self.shared.recording_raw.value = 1
        else:
            self.shared.recording_raw.value = 0

    def toggle_snapshot_repeat(self, checked):
        if checked:
            self.snapshot_timer.start(1000)
        else:
            self.snapshot_timer.stop()

    def closeEvent(self, event):
        self.shared.running.value = 0
        event.accept()

    def take_snapshot(self):

        self.snapshot_idx += 1

        images = [Image.fromarray(self.get_image_from_camera(self.shared.images_raw, cam)) for cam in
                  self.shared.camera_names]

        for idx, cam in enumerate(self.shared.camera_names):
            file_name = "./{0}-{1}.png".format(idx + 1, self.snapshot_idx)
            images[idx].save(join(self.shared.data_folder, "snapshot", file_name))

    def write_metadata(self):

        # self.button_record.setEnabled(True)

        metadata = dict()

        metadata["project"] = str(self.selector_project.currentText())
        metadata["git_hash"] = str(self.shared.gsettings["git_hash"])
        metadata["genotype"] = str(self.md_genotype.text())
        metadata["notes"] = str(self.md_notes.toPlainText())
        metadata["experimenter"] = str(self.md_person.text())
        metadata["age"] = int(self.md_age.value())
        metadata["number"] = int(self.md_number.value())
        metadata["sex"] = str(self.md_sex.currentText())
        metadata["date"] = datetime.now()
        metadata["protocol_set"] = str(self.selector_protocol_set.currentText())
        metadata["protocol"] = str(self.selector_protocol.currentText())

        path = join(self.shared.data_folder, "metadata.yaml")
        with open(path, "wb") as file:
            yaml.dump(metadata, stream=file, default_flow_style=False)

    def set_protocol(self):
        pass

    def change_protocol_set(self, set_name):

        try:
            protocols = AVAILABLE_PROTOCOLS[set_name]["protocols"].keys()

            self.selector_protocol.clear()
            self.selector_protocol.addItems(protocols)
        except:
            pass
