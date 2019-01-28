import numpy as np
from numba import jit
import cv2
from munkres import munkres
from itertools import permutations
from sys import stdout

# Hungarian algorithm-based tracking system
# Adapted from Ardekani et al. 2013


### HELPER FUNCTIONS

@jit(nopython=True)
def cartesian_numba(n):
    """Returns the Cartesian product of range(n)"""

    out = np.zeros((n*n, 2)).astype(np.int64)
    for idx1 in range(n):
        for idx2 in range(n):
            oidx = idx1 * n + idx2
            out[oidx, 0] = idx1
            out[oidx, 1] = idx2
    return out


def count_above(arr, above=0):
    k, n = arr.shape
    out = np.zeros(n, dtype=np.int64)
    for nidx in range(n):
        subarr = arr[:, nidx]
        out[nidx] = (subarr[subarr >= above]).size
    return out


def munkres_safe(e):
    """Wrapper around Hungarian algorithm that allows infinite values"""

    e = e.copy()

    try:
        practicalInfinity = 2 * e[e < np.inf].max() + 1
    except ValueError:
        practicalInfinity = 1

    e[e == np.inf] = practicalInfinity
    e[e == -np.inf] = 0.0

    assignment = munkres(e)
    return np.argwhere(assignment)[:, 1]


### TRIANGULATION METHODS

@jit(nopython=True)
def fast_triangulation_numba(mat1, mat2, pts1, pts2):
    """Implementation of SVD-based triangulation method."""
    
    n_points = pts1.shape[1]
    mat_a = np.zeros((4, 4))

    pts = np.stack((pts1, pts2))
    mats = np.stack((mat1, mat2))

    output_pts = np.zeros((4, n_points))

    for pt_idx in range(n_points):

        for j in range(2):
            x, y = pts[j, 0, pt_idx], pts[j, 1, pt_idx]
            for k in range(4):
                mat_a[j*2+0, k] = x * mats[j, 2, k] - mats[j, 0, k]
                mat_a[j*2+1, k] = y * mats[j, 2, k] - mats[j, 1, k]

        w, u, v = np.linalg.svd(mat_a)
        output_pts[:, pt_idx] = v[3, :]

    return output_pts / output_pts[3, :]


@jit
def fast_triangulation_opencv(mat1, mat2, pts1, pts2):
    """OpenCV implementation of triangulation."""
    output_pts = cv2.triangulatePoints(mat1, mat2, pts1, pts2)
    return output_pts / output_pts[3, :]


@jit(nopython=True)
def multi_dot(a, B):
    pts = np.dot(a, B)
    return pts[:2, :] / pts[2, :]


def multi_dist(a, b):
    return np.sqrt(np.sum((a - b) ** 2, axis=0))


@jit
def backprojection_error(m1, m2, pts1, pts2):
    """Calculates backprojection error after triangulation."""

    pts3d = fast_triangulation_opencv(m1, m2, pts1, pts2)

    bp1 = multi_dot(m1, pts3d)
    bp2 = multi_dot(m2, pts3d)

    dists = 0.5 * (multi_dist(bp1, pts1) + multi_dist(bp2, pts2))

    # Fix errors for NaN:
    nan_mask1 = np.isnan(pts1[0, :])
    nan_mask2 = np.isnan(pts2[0, :])

    dists[np.logical_and(nan_mask1, nan_mask2)] = -np.inf
    dists[np.logical_xor(nan_mask1, nan_mask2)] = np.inf

    return dists


## SEQH MACHINERY

@jit
def generate_error_matrix(ms, pts):
    """Populates the error matrix using backprojection of current assignment to targets."""

    # Pre-allocate matrix:
    k, n = pts.shape[0], pts.shape[1]
    e = np.zeros((k, k, n, n)) * np.NaN

    idx_select = cartesian_numba(n)

    for kidx1 in np.arange(k - 1):
        for kidx2 in np.arange(kidx1 + 1, k):
            m1, m2 = ms[kidx1, :, :], ms[kidx2, :, :]

            pt_buffer1 = pts[kidx1, idx_select[:, 0], :].T
            pt_buffer2 = pts[kidx2, idx_select[:, 1], :].T

            errs = backprojection_error(m1, m2, pt_buffer1, pt_buffer2).reshape((n, n))
            e[kidx1, kidx2, :, :] = errs
            e[kidx2, kidx1, :, :] = errs.T

    return e


@jit(nopython=True)
def gather_errors(current_camera, assignments, error_matrix):

    k, n = assignments.shape
    errors = np.zeros((n, n))

    for idx1 in range(n):  # in 3D point coordinates

        current_matching = assignments[:, idx1]

        for idx2 in range(n):  # in per-camera 2D point coordinates
            overall_error = 0.0
            for pt_idx in range(k):
                if (current_matching[pt_idx] >= 0) and (pt_idx != current_camera):
                    ck, cn = pt_idx, current_matching[pt_idx]
                    curr_error = error_matrix[ck, current_camera, cn, idx2]
                    overall_error += curr_error
            errors[idx1, idx2] = overall_error

    return errors


@jit(nopython=True)
def update_matching(pts, assignments, matching, current_camera, local_errors, threshold):

    n = assignments.shape[1]

    for update_idx in range(n):
        curr_err = local_errors[update_idx, matching[update_idx]]
        if np.isfinite(curr_err):
            if curr_err < threshold:
                assignments[current_camera, update_idx] = matching[update_idx]
        else:
            match_ks = (assignments[:, update_idx] >= 0).nonzero()[0]
            if len(match_ks) == 1:
                ck = match_ks[0]
                cn = assignments[ck, update_idx]
                if np.isnan(pts[ck, cn, 0]) and not np.isnan(pts[current_camera, matching[update_idx], 0]):
                    assignments[:, update_idx] = -1
                    assignments[current_camera, update_idx] = matching[update_idx]


@jit(nopython=True)
def calculate_matching_cost(pts, assignment, error_matrix, failure_penalty):

    overall_cost = 0.0
    failures = 0

    k, n = assignment.shape

    for nidx in range(n):
        matching = assignment[:, nidx]
        if len(matching[matching >= 0]) < 2:
            failures += 1
        else:
            for kidx1 in range(k):
                for kidx2 in range(k):
                    if kidx1 != kidx2:
                        pt1, pt2 = matching[kidx1], matching[kidx2]
                        if pt1 >= 0 and pt2 >= 0:
                            overall_cost += error_matrix[kidx1, kidx2, pt1, pt2]

    return overall_cost + failure_penalty * failures


@jit
def step(ms, pts, permutation, error_matrix, threshold):
    
    k, n = pts.shape[0], pts.shape[1]
    assignments = np.ones((k, n)).astype(np.int64) * -1

    assignments[permutation[0], :] = range(n)

    for cidx in range(1, k):
        
        current_camera = permutation[cidx]

        # Construct error matrix:
        local_errors = gather_errors(current_camera, assignments, error_matrix)
        
        # Calculate matching:
        matching = munkres_safe(local_errors)

        # Update C:
        update_matching(pts, assignments, matching, current_camera, local_errors, threshold)

    return assignments


@jit
def match(ms, pts, threshold=None, failure_penalty=100000):

    k, n = pts.shape[:2]
    assert k == ms.shape[0]

    perms = list(permutations(range(k)))
    error_matrix = generate_error_matrix(ms, pts)

    if threshold is None:
        threshold = np.inf

    matchings = np.zeros((len(perms), k, n)).astype(np.int64)
    costs = np.zeros(len(perms))

    for pidx in range(len(perms)):
        matchings[pidx, :, :] = step(ms, pts, perms[pidx], error_matrix, threshold)
        costs[pidx] = calculate_matching_cost(pts, matchings[pidx, :, :], error_matrix, failure_penalty)

    min_idx = np.argmin(costs)
    return matchings[min_idx, :, :]


### WRAPPER CLASS

class FastSeqH(object):

    def __init__(self, camera_system, minimum_tracks=3, failure_penalty=100000, threshold=None):
        self.camera_system = camera_system
        self.camera_names = self.camera_system.get_names()
        self.ms = np.array(
            [self.camera_system.get_camera(camera_name).get_M() for camera_name in self.camera_system.get_names()])

        self.minimum_tracks = minimum_tracks
        self.failure_penalty = failure_penalty
        self.threshold = threshold

    def _transform_points(self, pt_dic, undistort):

        max_n = max([p.shape[0] for p in pt_dic.itervalues()])
        pts = np.ones((len(self.camera_names), max_n, 2)) * np.nan

        for cidx, name in enumerate(self.camera_names):
            pts_ = pt_dic[name]

            if np.all(np.isnan(pts_)):
                continue

            if undistort:
                current_camera = self.camera_system.get_camera(name)
                pts_ = current_camera.undistort(pts_)

            n = pts_.shape[0]
            pts[cidx, :n, :] = pts_

        return pts

    def _triangulate_point(self, pts, matching, diagnostics=False):

        k_take = np.where(matching >= 0)[0].astype(np.int)
        pt_collection = [(self.camera_names[kidx], np.atleast_2d(pts[kidx, matching[kidx], :])) for kidx in k_take]
        pt3d = self.camera_system.find3d(pt_collection, undistort=False)

        if diagnostics:
            error = self._reconstruction_error(pt3d, pt_collection)
        else:
            error = np.nan

        return pt3d, error

    def _reconstruction_error(self, pt3d, points):

        # Project out to cameras:
        errors = []
        for name, initial_point in points:
            pt2d = self.camera_system.find2d(name, pt3d, distorted=False)
            errors.append(np.linalg.norm(pt2d - initial_point))
        errors = np.array(errors)

        # Calculate average error:
        error = errors.mean()

        return error

    def reconstruct(self, pt_dic, diagnostics=False, undistort=True):

        # Prepare data:
        pts = self._transform_points(pt_dic, undistort)

        # Reconstruct:
        matching = match(self.ms, pts, threshold=self.threshold, failure_penalty=self.failure_penalty)

        # Filter:
        filter_mask = count_above(matching) >= self.minimum_tracks
        matching_filtered = matching[:, filter_mask]

        # Triangulate:
        pts_triangulated = []
        pts_error = []

        for nidx in range(matching_filtered.shape[1]):
            pt_triangulated, pt_error = self._triangulate_point(pts, matching_filtered[:, nidx], diagnostics=diagnostics)
            pts_triangulated.append(pt_triangulated)
            pts_error.append(pt_error)

        return np.array(pts_triangulated), np.array(pts_error)
