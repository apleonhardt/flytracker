import flycapture2 as cap

AVAILABLE_PROPS = {
    "brightness": cap.BRIGHTNESS,
    "exposure": cap.AUTO_EXPOSURE,
    "sharpness": cap.SHARPNESS,
    "gamma": cap.GAMMA,
    "shutter": cap.SHUTTER,
    "gain": cap.GAIN,
    "framerate": cap.FRAME_RATE,
}

NO_ABSOLUTE_PROPS = ["sharpness"]


def get_camera_number():
    temp_context = cap.Context()
    return temp_context.get_num_of_cameras()


class PGCamera(object):
    """Wrapper for flycapture2."""

    def __init__(self, serial_number):
        self.context = cap.Context()
        self.connected = False
        self.serial_number = serial_number
        self.image_buffer = cap.Image()

    def __del__(self):
        if self.connected:
            self.disconnect()

    def connect(self):
        """Connects to the camera specified during object construction."""

        self.context.connect(*self.context.get_camera_from_serial_number(self.serial_number))
        self.connected = True

        return True

    def disconnect(self):
        """Disconnects the camera."""

        self.context.stop_capture()
        self.context.disconnect()

        self.connected = False

        return True

    def get_camera_info(self):
        return self.context.get_camera_info() if self.connected else {}

    def start_capture(self):
        """Starts image acquisition"""

        self.context.start_capture()
        return True

    def stop_capture(self):
        """Stops image acquisition"""

        self.context.stop_capture()
        return True

    def grab(self):
        """Grabs a single image from camera buffer."""

        self.context.retrieve_buffer(self.image_buffer)
        return self.image_buffer

    def get_format_info(self, mode):
        return self.context.get_format7_info(mode)

    def get_format_configuration(self):
        return self.context.get_format7_configuration()

    def set_format_configuration(self, mode, offset_x, offset_y, width, height):
        self.context.set_format7_configuration(mode, offset_x, offset_y, width, height, cap.PIXEL_FORMAT_MONO8)
        return True

    def get_trigger(self):
        return self.context.get_trigger_mode()

    def set_trigger(self, on_off):
        current_trigger = self.get_trigger()
        current_trigger["on_off"] = on_off
        self.context.set_trigger_mode(**current_trigger)
        return True

    def get_property_info(self, propname):
        return self.context.get_property_info(AVAILABLE_PROPS[propname])

    def get_property(self, propname):
        prop = self.context.get_property(AVAILABLE_PROPS[propname])
        return prop

    def get_property_value(self, propname):
        return self.get_property(propname)['abs_value']

    def set_property(self, prop):
        self.context.set_property(**prop)
        return True

    def set_property_value(self, propname, value):
        prop = self.get_property(propname)
        propinfo = self.get_property_info(propname)

        if propname in NO_ABSOLUTE_PROPS:

            mi, ma = propinfo["min"], propinfo["max"]
            value = min(max(mi, value), ma)

            prop["abs_control"] = False
            prop["value_a"] = value

        else:

            mi, ma = propinfo["abs_min"], propinfo["abs_max"]
            value = min(max(mi, value), ma)

            prop["abs_control"] = True
            prop["abs_value"] = value

        prop["auto_manual_mode"] = False
        prop["on_off"] = True
        prop["one_push"] = False

        self.context.set_property(**prop)
        return True

    def set_property_values(self, properties):
        [self.set_property_value(propname, value) for propname, value in properties.iteritems() if
         propname in AVAILABLE_PROPS]
        return True

    def print_all_properties(self):

        for prop, code in AVAILABLE_PROPS.viewitems():
            info = self.get_property(prop)
            print "{0}:\t\t".format(prop), info
