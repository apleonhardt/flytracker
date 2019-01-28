import Tkinter, tkFileDialog

from os.path import join

from pymvg.camera_model import CameraModel
from pymvg.multi_camera_system import MultiCameraSystem
from pymvg.plot_utils import plot_system, plot_camera
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

from pickle import load

from scipy.io import loadmat

from settings import cam_settings

CALIB = r""

if __name__ == "__main__":

    # root = Tkinter.Tk()
    # root.withdraw()
    #
    # CALIB = tkFileDialog.askdirectory()

    calib_id = load(open(join(CALIB, "camid.data"), 'r'))
    calib = loadmat(join(CALIB, "calibration.mat"), squeeze_me=True)['cameras']

    cameras = []

    for idx in range(len(calib_id)):
        print ""
        print "~~~~~~~~~~~~~~~~~~~~~~~~~~"
        print "Importing {0}".format(calib_id[idx])

        pmat = calib[idx][0]
        distortion = calib[idx][1]
        name = calib_id[idx]
        width = cam_settings[name]["f7"]["width"]
        height = cam_settings[name]["f7"]["height"]

        print pmat
        print distortion

        camera = CameraModel.load_camera_from_M(pmat, width=width, height=height, name=name,
                                                distortion_coefficients=distortion)

        cameras.append(camera)

    system = MultiCameraSystem(cameras)
    system.save_to_pymvg_file(join(CALIB, "camera_system.json"))

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # plot_system(ax, system)
    for name in system.get_names():
        plot_camera(ax, system.get_camera(name))

    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    plt.show()