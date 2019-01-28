from os import path, makedirs

import numpy as np
import pandas as pd
import cv2
from tqdm import tqdm_notebook


def render_projection_video(camera_system, cam_id, data_path, tracked, twod, upto=None):

    # Create directory iff it doesn't exist:
    dirname = path.join(data_path, "diagnostics")
    if not path.exists(dirname):
        makedirs(dirname)

    # Load up video:
    r = cv2.VideoCapture(path.join(data_path, "raw", "Cam{0}.avi".format(cam_id)))
    width, height = int(r.get(cv2.CAP_PROP_FRAME_WIDTH)), int(r.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = r.get(cv2.CAP_PROP_FPS)

    # Load frame IDs:
    frame_n = pd.read_csv(path.join(data_path, "raw", "Cam{0}.csv".format(cam_id))).frame_number

    fourcc = cv2.VideoWriter_fourcc(*"X264")
    filename = path.join(data_path, "diagnostics", "Cam{0}_tracked.avi".format(cam_id))
    w = cv2.VideoWriter(filename, fourcc, fps, (width, height), isColor=True)

    if upto is None:
        upto = frame_n.max()

    failures = []

    my2d = twod.xs(cam_id, level="camera_id").sort_index()

    for frame_idx in tqdm_notebook(range(upto)):

        retval, current_frame = r.read()

        if not retval:
            break

        # current_frame = cv2.cvtColor(current_frame, cv2.COLOR_GRAY2BGR)

        # Pick targets:
        frame_ = frame_n[frame_idx]

        if frame_ in tracked.index:
            try:
                targets = tracked.xs(frame_, level="frame_number")
            except:
                targets = tracked.loc[[frame_]]

            # Render:
            for index, target in targets.iterrows():
                pt = np.array([[target.x, target.y, target.z]])
                proj = camera_system.find2d(cam_id, pt, distorted=True).squeeze().astype(np.uint)

                try:
                    cv2.circle(current_frame, tuple(proj), 5, (0, 0, 255))
                except OverflowError:
                    failures.append(frame_idx)

        if frame_ in my2d.index:
            targets = my2d.loc[frame_:frame_]
            # print targets.shape

            # Render:
            for index, target in targets.iterrows():
                cv2.circle(current_frame, (int(target.x), int(target.y)), 8, (255, 0, 0))

        # Write frame number:
        cv2.putText(current_frame , "#{0}".format(frame_idx), (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255))

        w.write(current_frame)

    failures = np.array(failures)

    w.release()
    r.release()

    return failures
