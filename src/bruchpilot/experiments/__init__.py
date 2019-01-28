# This module acts as a stimulus directory -- stimuli defined here are available
# from the GUI.

from .base import *

AVAILABLE_PROTOCOLS = {
    "optomotor_project": {
        "name": "Optomotor stimuli",
        "lead": "Aljoscha",

        "protocols": {
            "grating_fixed": [GratingStimulus, dict(lam=20.0, vel=0.0)],
            "grating_cw": [GratingStimulus, dict(lam=20.0, vel=-20.0)],
            "grating_ccw": [GratingStimulus, dict(lam=20.0, vel=20.0)],

            "checker_fixed": [RandomCheckerStimulus, dict(checker_size=5.0)],
            "checker_cw_40": [RandomCheckerStimulus, dict(checker_size=5.0, vel=-40.0)],
            "checker_ccw_40": [RandomCheckerStimulus, dict(checker_size=5.0, vel=40.0)],
        }

    },
    "optogenetics_project": {
        "name": "Optogenetic stimuli",
        "lead": "Alex Mauss",

        "protocols": {
            "static_background_white": [GratingStimulus, dict(c_high=255.0, c_low=255.0, color=(1.0, 1.0, 1.0))],
            "static_background_gray": [GratingStimulus, dict(c_high=50.0, c_low=50.0, color=(1.0, 1.0, 1.0))],
            "static_background_red": [GratingStimulus, dict(c_high=255.0, c_low=255.0, color=(1.0, 0.0, 0.0))],
            "static_background_green": [GratingStimulus, dict(c_high=255.0, c_low=255.0, color=(0.0, 1.0, 0.0))],
            "static_background_blue": [GratingStimulus, dict(c_high=255.0, c_low=255.0, color=(0.0, 0.0, 1.0))],

            "checker_fixed_opto": [RandomCheckerOptoStimulus,
                                   dict(checker_size=5.0, opto_intensities=(2500, 0), switch_schedule=(1.0, 5.0))]
        }
    }
}
