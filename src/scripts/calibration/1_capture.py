from settings import cam_settings

import sys
import time
import os
from pickle import dump

import numpy as np
import cv2

conc = np.concatenate

sys.path.append("../..")
from bruchpilot.peripheral.framesync import FrameSync
from bruchpilot.peripheral.camera import PGCamera

BASE_PATH = r""

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

    foldername = str(int(time.time()))
    full_folder = os.path.join(BASE_PATH, foldername)
    os.makedirs(full_folder)

    print "Writing to ", full_folder

    # Set up sync:
    sync = FrameSync()
    sync.set_framerate(30, duty_cycle=0.5)
    sync.start()

    time.sleep(1)

    cams = [set_up_camera(sn) for sn in cam_settings.keys()]
    camid = [cam.get_camera_info()["serial_number"] for cam in cams]

    # Store camid:
    dump(camid, open(os.path.join(full_folder, "camid.data"), "w"))

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
            frames_edit.append(cv2.resize(image, (320, 256)))

        # Hack:
        vis = conc(frames_edit, axis=1)

        count += 1
        now = time.time()
        elapsed = now - starttime

        if elapsed >= update_rate:
            fps = count / elapsed
            starttime = now
            count = 0

            [cv2.imwrite(os.path.join(full_folder, "{1}-{0}.png".format(save_idx + 1, idx + 1)), frames[idx]) for idx in
             range(len(cams))]
            save_idx += 1
            print "Wrote picture series #{0}!".format(save_idx)

        cv2.putText(vis, "FPS: {0:.2f} Hz".format(fps), (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 255)
        cv2.imshow("viewer", cv2.resize(vis, None, fx=ffac, fy=ffac))

        key = cv2.waitKey(5)
        if key == 27:
            break

    [cam.disconnect() for cam in cams]
    cv2.destroyAllWindows()
