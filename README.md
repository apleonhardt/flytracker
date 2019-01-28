# 3D fly tracking system

Aljoscha Leonhardt (leonhardt@neuro.mpg.de, Borst Lab, MPI of Neurobiology)

This is code for a 3D fly tracking arena that allows simultaneous monitoring of multiple _Drosophila_ as well as real-time display of 3D stimuli. Note that this software is not optimized to be usable on arbitrary set-ups and unfortunately we currently don't provide instructions for setting up custom systems. A more recent version that includes CNN-based fly extraction will be released along with a forthcoming paper.

Some critical prerequisites:

* Python 2.7
* `numpy`, `pandas`, `numba`, `scipy`
* OpenCV > 2.4.11
* Qt and PyQt
* Panda3D

Important modules in `src`:

* `bruchpilot/modules`: Core system
    * `gui.py`: User interface
    * `camera.py`: Camera management and image processing
    * `opto.py`: Tools for optogenetic control
    * `stimulus.py`: Framework for displaying visual stimuli
    * `trigger.py`: Tools for triggering the camera array
    * `shared.py`: Inter-process communication
* `bruchpilot/peripheral`: Library for communicating with PointGrey cameras and the trigger system
* `bruchpilot/tracking`:
    * `reconstruct_fast.py`: Implementation of a 3D reconstruction tool based on the Hungarian algorithm (adapted from Ardekani et al., 2013), optimized via `numba`
    *  `tracker.py`: Simple Kalman tracker
* `scripts`: Tools for calibration and post-processing of data 