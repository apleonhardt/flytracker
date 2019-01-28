import serial
from serial.tools.list_ports import grep

__version__ = "0.0.1"

DEVICE_NAME = "A501M1XS"
BAUD_RATE = 76800
TIME_RESOLUTION = 0.0001


def bounded(val, high=99999, low=0):
    return min(max(val, low), high)


class ExternalController(object):
    """Generic interface to USB devices that emit TTL signals."""

    def __init__(self, device_name=None, baud_rate=None):

        self.conn = None

        # Find device:
        devices = list(grep(device_name or DEVICE_NAME))
        if len(devices) != 1:
            raise Exception("Couldn't find USB device!")
        ident = devices[0][0]

        # Open connection:
        self.conn = serial.Serial(port=ident, baudrate=baud_rate or BAUD_RATE, timeout=2)
        if not self.conn.isOpen():
            raise Exception("Could not establish connection!")

        self.connected = True

    def __del__(self):
        if self.conn:
            self.conn.close()

    def _set_value(self, command, value):
        self.conn.write("1{0}{1:05d}\r".format(command, int(value)))
        ret = self.conn.read(1)
        return ret == 'c'

    def _get_value(self, command):
        self.conn.write("0{0}00000\r".format(command))
        return int(self.conn.read(5))

    # Functions:

    def close(self):
        self.conn.close()


class OptogeneticLight(ExternalController):
    def __init__(self, device_name, baud_rate=None):
        super(OptogeneticLight, self).__init__(device_name, baud_rate)

    def set_global_intensity(self, intensity):
        intensity = bounded(intensity)
        return self._set_value("S", intensity)

    def set_specific_intensity(self, led_id, intensity):
        intensity = bounded(intensity)
        return self._set_value(str(led_id), intensity)

    def get_intensity(self, global_setting=True):
        if global_setting:
            return self._get_value("S")
        else:
            return [self._get_value(str(idx)) for idx in range(1, 10)]


class FrameSync(ExternalController):
    def __init__(self, device_name=None, baud_rate=None):
        super(FrameSync, self).__init__(device_name, baud_rate)

    def start(self):
        return self._set_value("S", 1)

    def stop(self):
        return self._set_value("S", 0)

    def set_framerate(self, framerate, duty_cycle=0.2):

        # Calculate high/low:
        duty_cycle = bounded(duty_cycle, low=0, high=1)
        period = 1.0 / framerate
        high, low = duty_cycle * period, (1.0 - duty_cycle) * period

        # Transform into appropriate values:
        dt = TIME_RESOLUTION  # Time resolution of generating device
        high_, low_ = bounded(int(high / dt)), bounded(int(low / dt))

        a, b = self._set_value("L", low_), self._set_value("H", high_)
        return a and b
