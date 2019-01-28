import sys
from os import path
import os
import tempfile
from shutil import copy2
import argparse
from multiprocessing import Pool, Lock

import numpy as np
import pandas as pd
from tqdm import tqdm
from pymvg.multi_camera_system import MultiCameraSystem

sys.path.append("../../")
from bruchpilot.tracking.tracker import Tracker


def load_data(data_path):
    data_path_full = path.join(data_path, "reconstruction", "points.csv")
    data = pd.read_csv(data_path_full).set_index(["frame_number", "point_id"])
    return data


def main(args):
    
    if not path.exists(args.data):
        raise ValueError("Data path does not exist!")

    output_path = path.join(args.data, "reconstruction", "tracked.csv")

    storage_file = tempfile.NamedTemporaryFile(mode="wb", delete=False)
    tracker = Tracker(storage_file=storage_file, maximum_distance=args.maximum_distance,
                      maximum_missed_frames=args.maximum_missed, dt=args.delta)

    print "Loading and filtering data (to temporary file {0})...".format(storage_file.name)
    data = load_data(args.data)
    data = data[data.reconstruction_error < args.maximum_reconstruction_error]

    print "Tracking..."
    tracker.process_batch(data, start=args.range[0], stop=args.range[1], pg_mode="terminal")

    storage_file.close()
    copy2(storage_file.name, output_path)
    os.remove(storage_file.name)


if __name__ == "__main__":

    parser = argparse.ArgumentParser("Tracking helper for retrieving individual fly paths from 3D points")

    parser.add_argument("--data", action="store", type=str)
    parser.add_argument("--range", type=int, nargs=2, action="store", default=[None, None])
    parser.add_argument("--maximum-reconstruction-error", action="store", type=float, default=5.0)
    parser.add_argument("--maximum-distance", action="store", type=float, default=1.0)
    parser.add_argument("--maximum-missed", action="store", type=int, default=20)
    parser.add_argument("--delta", action="store", type=float, default=0.01)

    args = parser.parse_args()
    main(args)
