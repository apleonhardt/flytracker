import sys

from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import loadPrcFileData, TrueClock, TextureStage

import numpy as np

from .helpers import create_color_texture, create_striped_texture, create_checker_texture


class StimulusBase(ShowBase):
    """Base class from which all stimuli inherit. Defines the global timing loop."""

    def __init__(self, shared):
        loadPrcFileData("",
                        """load-display pandagl
                        sync-video #t
                        fullscreen #f
                        win-origin 0 0
                        undecorated #t
                        cursor-hidden #t
                        win-size 7680 1080
                        show-frame-rate-meter #t
                        auto-single-cpu-affinity #f
                        """)

        TrueClock.getGlobalPtr().setCpuAffinity(0xFFFFFFFF)

        self.shared = shared

        ShowBase.__init__(self)

        self.global_time = 0.0

        self.statustex1 = create_color_texture([0, 0, 0])
        self.statustex2 = create_color_texture([255, 255, 255])

        self.statusimage1 = OnscreenImage(self.statustex1, scale=(0.015, 0.015, 0.015), sort=20,
                                          pos=(self.getAspectRatio() - 0.01, 0, -1 + 0.01))

        self.taskMgr.add(self.loop, "Primary loop")

        # Calibration details:
        self.calibrated_length = 4 * 56.9

    def loop(self, task):

        self.global_time += globalClock.getDt()

        # Run actual stimulus:
        self.update_stimulus(task.frame, self.global_time)

        # Flip flicker test:
        self.update_status(task.frame)

        if self.shared.running.value == 1:
            return task.cont
        else:
            self.destroy()
            sys.exit()
            return task.done

    def update_status(self, frame_number):
        if frame_number % 2 == 0:
            self.statusimage1.setTexture(self.statustex1)
        else:
            self.statusimage1.setTexture(self.statustex2)

    def update_stimulus(self, frame_number, time):
        pass


class GratingStimulus(StimulusBase):
    """Simple sine grating stimulus."""

    def __init__(self, shared,
                 lam=10.0, vel=10.0, c_high=255, c_low=0, color=(1.0, 1.0, 1.0)):
        StimulusBase.__init__(self, shared)

        # Parameters:

        self.param_lambda = lam  # cm
        self.param_velocity = vel  # cm/s
        self.param_c_high = c_high
        self.param_c_low = c_low
        self.param_color = np.array(color)

        # Set up simple image with grating:
        c1, c2 = self.param_color * self.param_c_low, self.param_color * self.param_c_high
        self.texture_grating = create_striped_texture(c1, c2, nearest=True)
        self.image_grating = OnscreenImage(self.texture_grating,
                                           pos=(0, 0, 0),
                                           scale=(self.getAspectRatio(), 1.0, 1.0),
                                           hpr=(0, 0, 0))

        self.image_grating.setTexOffset(TextureStage.getDefault(), 0.0, 0.0)
        self.image_grating.setTexScale(TextureStage.getDefault(), self.calibrated_length / self.param_lambda)

    def update_stimulus(self, frame_number, time):
        offset = (self.param_velocity * time) / self.param_lambda % 1
        self.image_grating.setTexOffset(TextureStage.getDefault(), offset, 0.0)


class RandomCheckerStimulus(StimulusBase):
    """Simple random checkerboard stimulus."""

    def __init__(self, shared,
                 checker_size=10.0, vel=0.0, c_high=255, c_low=0):
        StimulusBase.__init__(self, shared)

        # Parameters:

        self.param_checker_size = checker_size
        self.param_vel = vel
        self.param_c_high = c_high
        self.param_c_low = c_low

        # Set up texture:
        shape_horizontal = int(self.calibrated_length / self.param_checker_size)
        shape_vertical = int(shape_horizontal / self.getAspectRatio())

        self.texture_checkers = create_checker_texture(self.param_c_low, self.param_c_high,
                                                       (shape_vertical, shape_horizontal))
        self.image_checkers = OnscreenImage(self.texture_checkers,
                                            pos=(0, 0, 0),
                                            scale=(self.getAspectRatio(), 1.0, 1.0),
                                            hpr=(0, 0, 0))

        self.image_checkers.setTexOffset(TextureStage.getDefault(), 0.0, 0.0)

    def update_stimulus(self, frame_number, time):
        offset = (self.param_vel * time) / self.calibrated_length % 1
        self.image_checkers.setTexOffset(TextureStage.getDefault(), offset, 0.0)


class RandomCheckerOptoStimulus(StimulusBase):
    """Checkerboard stimulus that combines visual display with optogenetic activation,
    controlled by opto_intensities and switch_schedule."""

    def __init__(self, shared,
                 checker_size=10.0, vel=0.0, c_high=255, c_low=0,
                 opto_intensities=(4050, 0), switch_schedule=(10.0, 50.0)):
        StimulusBase.__init__(self, shared)

        # Parameters:

        self.param_checker_size = checker_size
        self.param_vel = vel
        self.param_c_high = c_high
        self.param_c_low = c_low

        self.opto_intensities = opto_intensities
        self.opto_switch_schedule = switch_schedule

        # Set up texture:
        shape_horizontal = int(self.calibrated_length / self.param_checker_size)
        shape_vertical = int(shape_horizontal / self.getAspectRatio())

        self.texture_checkers = create_checker_texture(self.param_c_low, self.param_c_high,
                                                       (shape_vertical, shape_horizontal))
        self.image_checkers = OnscreenImage(self.texture_checkers,
                                            pos=(0, 0, 0),
                                            scale=(self.getAspectRatio(), 1.0, 1.0),
                                            hpr=(0, 0, 0))

        self.image_checkers.setTexOffset(TextureStage.getDefault(), 0.0, 0.0)

        # Set up opto logic:
        self.opto_toggle = False
        self.last_checkpoint = 0.0
        self.shared.opto_intensity.value = self.opto_intensities[1]

    def update_stimulus(self, frame_number, time):

        offset = (self.param_vel * time) / self.calibrated_length % 1
        self.image_checkers.setTexOffset(TextureStage.getDefault(), offset, 0.0)

        # Opto logic:
        # self.opto_toggle allows for continuous switching between the two states, ON and OFF

        time_elapsed = time - self.last_checkpoint
        if self.opto_toggle and (time_elapsed >= self.opto_switch_schedule[0]):
            self.opto_toggle = False
            self.shared.opto_intensity.value = self.opto_intensities[1]
            self.last_checkpoint = time
        elif (not self.opto_toggle) and (time_elapsed >= self.opto_switch_schedule[1]):
            self.opto_toggle = True
            self.shared.opto_intensity.value = self.opto_intensities[0]
            self.last_checkpoint = time
