import sys
import time
from os import path

import numpy as np
from matplotlib import pyplot as plt
from skimage.exposure import equalize_adapthist
from pymvg.multi_camera_system import MultiCameraSystem
from pymvg import align
from mpl_toolkits.mplot3d import Axes3D
from pymvg.plot_utils import plot_system, plot_camera

sys.path.append("../..")
from bruchpilot.peripheral.framesync import FrameSync
from bruchpilot.peripheral.camera import PGCamera
from bruchpilot.tracking.reconstruct_fast import FastSeqH

from settings import cam_settings


### MAKE SURE THESE SETTINGS ARE CORRECT:

CALIBRATED_COORDINATES = np.array([
    [0.0, 0.0, 0.0],  # Origin
    [15.6, 0.0, 0.0],  # Long side = x
    [0.0, 9.2, 0.0],  # Short side = y
])

BASE_CALIBRATION = r""

###


def dist(a, b):
    return np.linalg.norm(a-b)


def set_up_camera(sn):
    assert sn in cam_settings.keys()

    cam = PGCamera(sn)
    cam.connect()

    print cam.get_camera_info()

    cam_settings[sn]["shutter"] = 4.0

    cam.set_property_values(cam_settings[sn])
    cam.set_format_configuration(**cam_settings[sn]["f7"])
    cam.set_trigger(True)

    cam.start_capture()
    time.sleep(0.5)

    return cam


def take_images():
    sync = FrameSync()
    sync.set_framerate(30, duty_cycle=0.5)
    sync.start()

    time.sleep(1)

    cams = [set_up_camera(sn) for sn in cam_settings.keys()]
    camid = [cam.get_camera_info()["serial_number"] for cam in cams]

    frames = []
    for cidx, (cam_name, cam) in enumerate(zip(camid, cams)):
        image = np.array(cam.grab())
        frames.append(image.copy())

    [cam.disconnect() for cam in cams]

    return np.array(frames), camid


def run_point_select(camids, images):

    global_pts = []

    for cidx, camid in enumerate(camids):

        print camid

        fig = plt.figure()
        local_pts = []

        def callback(event):
            if event.button == 3:
                local_pts.append([event.xdata, event.ydata])
                print event.xdata, event.ydata
            if len(local_pts) >= 3:
                plt.close()

        fig.canvas.callbacks.connect('button_press_event', callback)
        image = equalize_adapthist(images[cidx, :, :])
        plt.imshow(image, cmap="gray", interpolation="nearest")
        plt.show()

        local_pts = np.array(local_pts)
        global_pts.append(local_pts)

    return np.array(global_pts)


def triangulate_points(camera_system, pts):
    camids = camera_system.get_names()
    rec = FastSeqH(camera_system)

    pt_dic = {"{0}".format(camids[camidx]): pts[camidx, :, :] for camidx in range(len(camids))}
    pts_triangulated, pts_error = rec.reconstruct(pt_dic, diagnostics=True)

    assert np.all(pts_error < 5.0)
    return pts_triangulated


def identify_points(pts):
    a, b, c = pts[0, :], pts[1, :], pts[2, :]
    d1, d2, d3 = dist(a, b), dist(b, c), dist(a, c)

    distances = np.array([d1, d2, d3])
    sorting = np.argsort(distances)

    if sorting[2] == 0:
        origin = c
        if sorting[1] == 1:
            # c, b, a
            far, near = b, a
        else:
            # c, a, b
            far, near = a, b
    elif sorting[2] == 1:
        origin = a
        if sorting[1] == 0:
            # a, b, c
            far, near = b, c
        else:
            # a, c, b
            far, near = c, b
    elif sorting[2] == 2:
        origin = b
        if sorting[1] == 1:
            # b, c, a
            far, near = c, a
        else:
            # b, a, c
            far, near = a, c

    return np.array([origin, far, near])


def plot_reprojection(camera_system, images, points):
    colors = ['red', 'green', 'blue']
    desc = ['Origin', '+X', '+Y']

    for idx in range(images.shape[0]):
        plt.figure()
        plt.imshow(images[idx, :, :])

        for pidx in range(3):
            backprojected = camera_system.find2d(camera_system.get_names()[idx], points[pidx, :], distorted=True)
            plt.scatter(backprojected[0], backprojected[1], color=colors[pidx], label=desc[pidx])

        plt.legend()
        plt.show()


def transform_system(old, s, R, T):
    new_cams = []
    for name in old.get_names():
        orig_cam = old.get_camera(name)
        new_cam = orig_cam.get_aligned_camera(s, R, T)
        new_cams.append(new_cam)
    return MultiCameraSystem(new_cams)


if __name__ == "__main__":

    images, camids = take_images()
    points = run_point_select(camids, images)

    # np.save("points", points)

    camera_system = MultiCameraSystem.from_pymvg_file(path.join(BASE_CALIBRATION, "camera_system.json"))

    # points = np.load("points.npy")
    final_points = triangulate_points(camera_system, points)
    sorted_points = identify_points(final_points)
    plot_reprojection(camera_system, images, sorted_points)

    s, R, T = align.estsimt(sorted_points.T, CALIBRATED_COORDINATES.T)
    new_system = transform_system(camera_system, s, R, T)

    new_system.save_to_pymvg_file(path.join(BASE_CALIBRATION, "camera_system_aligned.json"))

    # DEBUGGING:

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    plot_system(ax, new_system)
    ax.scatter(CALIBRATED_COORDINATES[:, 0], CALIBRATED_COORDINATES[:, 1], CALIBRATED_COORDINATES[:, 2])

    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')

    ax.set_xlim([-30, 30])
    ax.set_ylim([-30, 30])

    plt.show()

    # Show that backprojection works:
    names = new_system.get_names()
    for iidx in range(5):
        plt.figure()
        plt.imshow(images[iidx, :, :], cmap="gray", interpolation="nearest")
        for pidx in range(3):
            bp = new_system.find2d(names[iidx], CALIBRATED_COORDINATES[pidx, :])
            plt.scatter(bp[0], bp[1], color="green")
        plt.show()
