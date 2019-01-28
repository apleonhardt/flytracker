from settings import cam_settings

import sys
import time
import os
from pickle import dump

from pymvg.multi_camera_system import MultiCameraSystem

import numpy as np
import cv2

conc = np.concatenate

sys.path.append("../..")
from bruchpilot.peripheral.framesync import FrameSync
from bruchpilot.peripheral.camera import PGCamera

CALIBRATED_COORDINATES = np.array([
    [0.0, 0.0, 0.0],  # Origin
    [15.6, 0.0, 0.0],  # Long side = x
    [0.0, 9.2, 0.0],  # Short side = y
])

BASE_CALIB = r""

ffac = 1.0
splitter = 4


def set_up_camera(sn):
    assert sn in cam_settings.keys()

    cam = PGCamera(sn)
    cam.connect()

    print cam.get_camera_info()

    cam.set_property_values(cam_settings[sn])
    cam.set_format_configuration(**cam_settings[sn]["f7"])
    cam.set_trigger(True)

    cam.start_capture()
    time.sleep(0.5)

    return cam


if __name__ == "__main__":

    # Load Camera System:
    camsys = MultiCameraSystem.from_pymvg_file(BASE_CALIB)

    # Set up sync:
    sync = FrameSync()
    sync.set_framerate(30, duty_cycle=0.5)
    sync.start()

    time.sleep(1)

    cams = [set_up_camera(sn) for sn in cam_settings.keys()]
    camid = [cam.get_camera_info()["serial_number"] for cam in cams]

    cv2.namedWindow("viewer", cv2.WINDOW_AUTOSIZE)
    starttime = time.time()

    update_rate = 1.0
    count = 0
    fps = 0

    save_idx = 0

    while True:

        # Pull frame from camera:
        frames = []
        frames_edit = []
        for cidx, cam in enumerate(cams):
            image = np.array(cam.grab())
            frames.append(image.copy())
            cv2.putText(image, "Cam {0}".format(camid[cidx]), (30, image.shape[0] - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        255)

            my_camera = str(camid[cidx])
            for pidx in range(3):
                pt = CALIBRATED_COORDINATES[pidx, :]
                pt_proj = camsys.find2d(my_camera, pt).astype(np.int)
                cv2.circle(image, tuple(pt_proj), 5, (0, 0, 255))

            # frames_edit.append(cv2.resize(image, (320, 256)))
            frames_edit.append(image)

        # Hack:
        vis = conc(frames_edit, axis=1)

        count += 1
        now = time.time()
        elapsed = now - starttime

        if elapsed >= update_rate:
            fps = count / elapsed
            starttime = now
            count = 0

        cv2.putText(vis, "FPS: {0:.2f} Hz".format(fps), (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 255)
        cv2.imshow("viewer", cv2.resize(vis, None, fx=ffac, fy=ffac))

        key = cv2.waitKey(5)
        if key == 27:
            break

    [cam.disconnect() for cam in cams]
    cv2.destroyAllWindows()
