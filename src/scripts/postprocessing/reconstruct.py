import sys
from os import path
import os
import argparse
from multiprocessing import Pool, Lock

import numpy as np
import pandas as pd
from tqdm import tqdm
from pymvg.multi_camera_system import MultiCameraSystem


sys.path.append("../../")
from bruchpilot.tracking.reconstruct_fast import FastSeqH


def load_data(data_path, camera_system):
    names = camera_system.get_names()

    gather = []
    for name in names:
        pt_path = path.join(data_path, "tracking", "Cam{0}.csv".format(name))
        data = pd.read_csv(pt_path)
        data["camera_id"] = name
        gather.append(data)
        
    full_data = pd.concat(gather)
    fd = full_data.set_index(["camera_id", "frame_number"]).sort_index()

    return fd


def reconstruct_wrapper(df, rec, diagnostics):
    
    d = {}
    for name in rec.camera_system.get_names():
        pts = df.loc[name]
        pts_ = np.zeros((len(pts), 2))
        pts_[:, 0] = pts.x
        pts_[:, 1] = pts.y
        d[name] = pts_
        
    out = rec.reconstruct(d, diagnostics=diagnostics, undistort=True)

    if out[0].size > 0:
        df = pd.DataFrame(out[0], columns=['x', 'y', 'z'])
        df["point_id"] = range(out[0].shape[0])
        if diagnostics:
            df["reconstruction_error"] = out[1]
        df.set_index("point_id", inplace=True)
    else:
        df = pd.DataFrame()

    return df


def single_reconstruct(argtuple):
    data, rec, args, idx = argtuple
    tqdm.pandas(position=idx, leave=True)
    return data.groupby(["frame_number"]).progress_apply(reconstruct_wrapper,
                                                         rec=rec, diagnostics=args.diagnostics)


def split(data, n):
    frame_index = data.index.levels[1]
    split_ranges = np.array_split(frame_index, n)
    for s in split_ranges:
        d = data.loc[pd.IndexSlice[:, s[0]:s[-1]], :]
        yield d


def init_child(write_lock):
    tqdm.set_lock(write_lock)


def multi_reconstruct(data, rec, args):
    write_lock = Lock()
    pool = Pool(processes=args.cores, initializer=init_child, initargs=(write_lock,))
    n_frames = data.index.levels[1]
    result = pd.concat(pool.map(single_reconstruct, [(d, rec, args, idx) for idx, d in enumerate(split(data, args.cores))]))
    pool.close()

    return result


def main(args):
    
    if not path.exists(args.data):
        raise ValueError("Data path does not exist!")

    # Load calibration:
    cam_path = path.join(args.data, "camera_system_aligned.json")
    camera_system = MultiCameraSystem.from_pymvg_file(cam_path)

    # Load data:
    data = load_data(args.data, camera_system)

    # Filter by area:
    data = data[data.area > args.area_filter]

    # Select a range:
    if args.frame_range is None:
        a, b = 0, data.index.levels[1].max()
    else:
        a, b = args.frame_range
    data = data.loc[pd.IndexSlice[:, a:b], :]

    data = data.reset_index().set_index(["camera_id", "frame_number"]).sort_index()

    # Set up reconstruction:
    rec = FastSeqH(camera_system, minimum_tracks=args.minimum_tracks)
    
    # Run:
    output = multi_reconstruct(data, rec, args).reset_index().set_index(["frame_number", "point_id"])

    # Save:
    output_directory = path.join(args.data, "reconstruction")
    if not path.exists(output_directory):
        os.mkdir(output_directory)
    
    output_path = path.join(output_directory, "points.csv")
    output.to_csv(output_path)


if __name__ == "__main__":

    parser = argparse.ArgumentParser("Reconstruction helper for triangulating from 2D to 3D")

    parser.add_argument("--data", action="store", type=str)
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--area-filter", action="store", type=float, default=0.0)
    parser.add_argument("--minimum-tracks", action="store", type=int, default=3)
    parser.add_argument("--cores", action="store", type=int, default=4)
    parser.add_argument("--frame-range", action="store", type=int, nargs=2)

    args = parser.parse_args()
    main(args)
