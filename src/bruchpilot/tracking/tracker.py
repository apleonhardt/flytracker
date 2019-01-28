import csv

import numpy as np
import pandas as pd
from filterpy.kalman import KalmanFilter
from munkres import munkres
from tqdm import tqdm_notebook, tqdm


def no_tqdm(x):
    return x


def euclidean_distance(pt1, pt2):
    return np.linalg.norm(pt1 - pt2)


class Target(object):
    """Representation of an individual Kalman filter object."""

    def __init__(self, target_id, starting_position, max_frames_without_observation, max_uncertainty, dt):

        self.id = target_id

        self.dt = dt
        self.is_alive = True
        self.frames_without_observation = 0
        self.max_frames = max_frames_without_observation
        self.max_P = max_uncertainty

        # Initialize Kalman filter:
        self.filter = KalmanFilter(dim_x=6, dim_z=3)

        self.filter.F = np.array([
            [1.0, dt, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, dt, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, dt],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ])  # Process matrix

        self.filter.H = np.array([
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        ])  # Observation matrix

        self.filter.R *= 2.0**2  # STD = 2cm

        Q_pos, Q_vel = 1.0**2, 50.0**2  # Straw parameters: STD_pos = 10mm, STD_vel = 50cm/s
        self.filter.Q = np.diag([Q_pos, Q_vel, Q_pos, Q_vel, Q_pos, Q_vel])

        P_pos, P_vel = 10.0**2, 100.0**2
        self.filter.P = np.diag([P_pos, P_vel, P_pos, P_vel, P_pos, P_vel])

        self.filter.x = np.array([
            starting_position[0], 0.0,
            starting_position[1], 0.0,
            starting_position[2], 0.0,
        ])

    def get_prediction(self):
        return self.filter.get_prediction()[0][[0, 2, 4]]

    def advance(self, observation=None):

        self.filter.predict()
        self.frames_without_observation += 1
        
        if observation is not None:
            self.filter.update(z=observation)
            self.frames_without_observation = 0
        
        if np.any(self.filter.P > self.max_P):
            self.is_alive = False

        if self.frames_without_observation > self.max_frames:
            self.is_alive = False

        return self.is_alive


class Tracker(object):
    """Basic Kalman Filter for target tracking."""

    def __init__(self, storage_file=None, maximum_distance=np.inf, maximum_missed_frames=np.inf,
                 maximum_uncertainty=np.inf, dt=0.01):
        
        self._targets = []

        self.standard_dt = dt
        self.max_distance = maximum_distance
        self.max_missed = maximum_missed_frames
        self.max_uncertainty = maximum_uncertainty

        self._next_target_id = 0

        # Set up storage:
        if storage_file:
            self._file = storage_file
            fieldnames = [
                "frame_number",
                "target_id",
                "n_missed_observations",
                "x",
                "x_variance",
                "x_velocity",
                "y",
                "y_variance",
                "y_velocity",
                "z",
                "z_variance",
                "z_velocity",
            ]
            self._storage = csv.DictWriter(self._file, fieldnames=fieldnames, extrasaction="ignore")
            self._storage.writeheader()
            self._document = True
        else:
            self._document = False

    def __del__(self):
        self._file.close()

    def _add_target(self, starting_position):

        self._next_target_id += 1
        new_target = Target(target_id=self._next_target_id, starting_position=starting_position,
                            max_frames_without_observation=self.max_missed,
                            max_uncertainty=self.max_uncertainty, dt=self.standard_dt)
        self._targets.append(new_target)

    def _calculate_matching_matrix(self, observations):
        incoming_n = observations.shape[0]
        target_n = len(self._targets)

        matching_matrix = np.zeros((target_n, incoming_n))

        predictions = [target.get_prediction() for target in self._targets]

        for target_idx in range(target_n):
            for observation_idx in range(incoming_n):
                observed_point = observations[observation_idx, :]
                error = euclidean_distance(predictions[target_idx], observed_point)
                matching_matrix[target_idx, observation_idx] = error

        return matching_matrix
        
    def process_frame(self, frame_number, observations):

        incoming_n = observations.shape[0]

        if len(self._targets) == 0:

            # No targets, so initialize everything:
            for idx in range(incoming_n):
                self._add_target(observations[idx, :])
            return
        
        elif incoming_n == 0:
            assignment = np.full((len(self._targets), 1), False, dtype=np.bool)
        
        else:
            # We have observations & targets, so matching is required:
            matching_matrix = self._calculate_matching_matrix(observations)
            assignment = munkres(matching_matrix)
            
        # Advance all targets:
        new_target_starts = []

        for tidx, target in enumerate(self._targets):

            my_match = assignment[tidx, :]
            if np.any(my_match):
                data_point = observations[my_match, :].squeeze()
                associated_cost = matching_matrix[tidx, my_match]
                if associated_cost > self.max_distance:
                    new_target_starts.append(data_point)
                    data_point = None
            else:
                data_point = None

            target.advance(data_point)

        # Clean out targets:
        self._targets = [target for target in self._targets if target.is_alive]

        # Create new targets:
        for starting_point in new_target_starts:
            self._add_target(starting_point)
        
        # Document what's happening:
        if self._document:
            for tidx, target in enumerate(self._targets):
                values = {}

                values["frame_number"] = frame_number
                values["target_id"] = target.id
                values["x"] = target.filter.x[0]
                values["y"] = target.filter.x[2]
                values["z"] = target.filter.x[4]
                values["x_velocity"] = target.filter.x[1]
                values["y_velocity"] = target.filter.x[3]
                values["z_velocity"] = target.filter.x[5]
                values["x_variance"] = target.filter.P[0, 0]
                values["y_variance"] = target.filter.P[2, 2]
                values["z_variance"] = target.filter.P[4, 4]
                values["n_missed_observations"] = target.frames_without_observation

                self._storage.writerow(values)

    def process_batch(self, frames, start=None, stop=None, pg_mode="notebook"):

        if stop is None:
            stop = frames.index.levels[0].max()
        if start is None:
            start = frames.index.levels[0].min()

        frames = frames[["x", "y", "z"]]

        if pg_mode == "terminal":
            my_tqdm = tqdm
        elif pg_mode == "notebook":
            my_tqdm = tqdm_notebook
        else:
            my_tqdm = no_tqdm

        for fidx in my_tqdm(range(start, stop), smoothing=0.9):
            if fidx in frames.index:
                # THIS IS SLOW: Make faster!
                frame = frames.xs(fidx, level="frame_number").values
            else:
                frame = np.zeros((0, 3))
            self.process_frame(fidx, frame)
