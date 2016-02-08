from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

from RPi import GPIO

from . import Pin
from .exc import (
    PinInvalidFunction,
    PinSetInput,
    PinFixedPull,
    )


class RPiGPIOPin(Pin):
    """
    Uses the `RPi.GPIO`_ library to interface to the Pi's GPIO pins. This is
    the default pin implementation if the RPi.GPIO library is installed.
    Supports all features including PWM (via software).

    .. _RPi.GPIO: https://pypi.python.org/pypi/RPi.GPIO
    """

    _PINS = {}

    GPIO_FUNCTIONS = {
        'input':   GPIO.IN,
        'output':  GPIO.OUT,
        'i2c':     GPIO.I2C,
        'spi':     GPIO.SPI,
        'pwm':     GPIO.PWM,
        'serial':  GPIO.SERIAL,
        'unknown': GPIO.UNKNOWN,
        }

    GPIO_PULL_UPS = {
        'up':       GPIO.PUD_UP,
        'down':     GPIO.PUD_DOWN,
        'floating': GPIO.PUD_OFF,
        }

    GPIO_EDGES = {
        'both':    GPIO.BOTH,
        'rising':  GPIO.RISING,
        'falling': GPIO.FALLING,
        }

    GPIO_FUNCTION_NAMES = {v: k for (k, v) in GPIO_FUNCTIONS.items()}
    GPIO_PULL_UP_NAMES = {v: k for (k, v) in GPIO_PULL_UPS.items()}
    GPIO_EDGES_NAMES = {v: k for (k, v) in GPIO_EDGES.items()}

    def __new__(cls, number):
        if not cls._PINS:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        try:
            return cls._PINS[number]
        except KeyError:
            self = super(RPiGPIOPin, cls).__new__(cls)
            cls._PINS[number] = self
            self._number = number
            self._pull = 'up' if number in (2, 3) else 'floating'
            self._pwm = None
            self._frequency = None
            self._duty_cycle = None
            self._bounce = -666
            self._when_changed = None
            self._edges = GPIO.BOTH
            GPIO.setup(self._number, GPIO.IN, self.GPIO_PULL_UPS[self._pull])
            return self

    def __repr__(self):
        return "GPIO%d" % self._number

    @property
    def number(self):
        return self._number

    def close(self):
        self.frequency = None
        self.when_changed = None
        GPIO.cleanup(self._number)

    def output_with_state(self, state):
        self._pull = 'floating'
        GPIO.setup(self._number, GPIO.OUT, initial=state)

    def input_with_pull(self, pull):
        if pull != 'up' and self._number in (2, 3):
            raise PinFixedPull('%r has a physical pull-up resistor' % self)
        try:
            GPIO.setup(self._number, GPIO.IN, self.GPIO_PULL_UPS[pull])
            self._pull = pull
        except KeyError:
            raise PinInvalidPull('invalid pull "%s" for pin %r' % (pull, self))

    def _get_function(self):
        return self.GPIO_FUNCTION_NAMES[GPIO.gpio_function(self._number)]

    def _set_function(self, value):
        if value != 'input':
            self._pull = 'floating'
        try:
            GPIO.setup(self._number, self.GPIO_FUNCTIONS[value], self.GPIO_PULL_UPS[self._pull])
        except KeyError:
            raise PinInvalidFunction('invalid function "%s" for pin %r' % (value, self))

    def _get_state(self):
        if self._pwm:
            return self._duty_cycle
        else:
            return GPIO.input(self._number)

    def _set_state(self, value):
        if self._pwm:
            try:
                self._pwm.ChangeDutyCycle(value * 100)
            except ValueError:
                raise PinInvalidValue('invalid state "%s" for pin %r' % (value, self))
            self._duty_cycle = value
        else:
            try:
                GPIO.output(self._number, value)
            except ValueError:
                raise PinInvalidState('invalid state "%s" for pin %r' % (value, self))
            except RuntimeError:
                raise PinSetInput('cannot set state of pin %r' % self)

    def _get_pull(self):
        return self._pull

    def _set_pull(self, value):
        if self.function != 'input':
            raise PinFixedPull('cannot set pull on non-input pin %r' % self)
        if value != 'up' and self._number in (2, 3):
            raise PinFixedPull('%r has a physical pull-up resistor' % self)
        try:
            GPIO.setup(self._number, GPIO.IN, self.GPIO_PULL_UPS[value])
            self._pull = value
        except KeyError:
            raise PinInvalidPull('invalid pull "%s" for pin %r' % (value, self))

    def _get_frequency(self):
        return self._frequency

    def _set_frequency(self, value):
        if self._frequency is None and value is not None:
            try:
                self._pwm = GPIO.PWM(self._number, value)
            except RuntimeError:
                raise PinPWMFixedValue('cannot start PWM on pin %r' % self)
            self._pwm.start(0)
            self._duty_cycle = 0
            self._frequency = value
        elif self._frequency is not None and value is not None:
            self._pwm.ChangeFrequency(value)
            self._frequency = value
        elif self._frequency is not None and value is None:
            self._pwm.stop()
            self._pwm = None
            self._duty_cycle = None
            self._frequency = None

    def _get_bounce(self):
        return None if self._bounce == -666 else (self._bounce / 1000)

    def _set_bounce(self, value):
        f = self.when_changed
        self.when_changed = None
        try:
            self._bounce = -666 if value is None else (value * 1000)
        finally:
            self.when_changed = f

    def _get_edges(self):
        return self.GPIO_EDGES_NAMES[self._edges]

    def _set_edges(self, value):
        f = self.when_changed
        self.when_changed = None
        try:
            self._edges = self.GPIO_EDGES[value]
        finally:
            self.when_changed = f

    def _get_when_changed(self):
        return self._when_changed

    def _set_when_changed(self, value):
        if self._when_changed is None and value is not None:
            self._when_changed = value
            GPIO.add_event_detect(
                self._number, self._edges,
                callback=lambda channel: self._when_changed(),
                bouncetime=self._bounce)
        elif self._when_changed is not None and value is None:
            GPIO.remove_event_detect(self._number)
            self._when_changed = None
        else:
            self._when_changed = value

