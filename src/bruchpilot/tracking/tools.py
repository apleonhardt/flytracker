import numpy as np


def generate_random_points(camsys, n, shuffle=True, dropout=0.0, distorted=True, noise=0.0):
    """Generates test points for tracking system."""

    k = len(camsys.get_names())

    pts = np.zeros((k, n, 2))
    pts_real = np.zeros((n, 3))
    pts_ass = np.zeros((k, n))

    for nidx in range(n):

        pt = np.random.randn(3)
        pts_real[nidx, :] = pt

        for camidx, camname in enumerate(camsys.get_names()):
            pts[camidx, nidx, :] = camsys.find2d(camname, pt, distorted=True)

    # Shuffle:
    for kidx in range(k):
        if shuffle:
            random_order = np.random.permutation(n)
        else:
            random_order = np.arange(n)

        pts_ass[kidx, :] = random_order
        pts[kidx, :, :] = pts[kidx, random_order, :]

        # Blank out final X entries:
        n_blank = np.random.poisson(lam=dropout * n)
        if n_blank > 0:
            pts[kidx, -n_blank:, :] = np.nan

    pts = pts + noise * np.random.normal(size=pts.shape)

    # Put into special format:
    names = camsys.get_names()
    pts_dict = {}
    for nidx, name in enumerate(names):
        pts_dict[name] = pts[nidx, ...].squeeze()

    return pts, pts_real, pts_ass, pts_dict
