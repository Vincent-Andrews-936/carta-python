"""This module provides miscellaneous utility classes and functions used by the wrapper."""

import logging
import json
import functools
import re

logger = logging.getLogger("carta_scripting")
logger.setLevel(logging.WARN)
logger.addHandler(logging.StreamHandler())


class CartaScriptingException(Exception):
    """The top-level exception for all scripting errors."""
    pass


class CartaBadSession(CartaScriptingException):
    """A session could not be constructed."""
    pass


class CartaBadID(CartaScriptingException):
    """A session ID is invalid."""
    pass


class CartaBadToken(CartaScriptingException):
    """A token has expired or is invalid."""
    pass


class CartaBadUrl(CartaScriptingException):
    """An URL is invalid."""
    pass


class CartaValidationFailed(CartaScriptingException):
    """Invalid parameters were passed to a function with a :obj:`carta.validation.validate` decorator."""
    pass


class CartaBadRequest(CartaScriptingException):
    """A request sent to the CARTA backend was rejected."""
    pass


class CartaRequestFailed(CartaScriptingException):
    """A request received a failure response from the CARTA backend."""
    pass


class CartaActionFailed(CartaScriptingException):
    """An action request received a failure response from the CARTA frontend."""
    pass


class CartaBadResponse(CartaScriptingException):
    """An action request received an unexpected response from the CARTA frontend."""
    pass


class Macro:
    """A placeholder for a target and a variable which will be evaluated dynamically by the frontend.

    Parameters
    ----------
    target : str
        The target frontend object.
    variable : str
        The variable on the target object.

    Attributes
    ----------
    target : str
        The target frontend object.
    variable : str
        The variable on the target object.
    """

    def __init__(self, target, variable):
        self.target = target
        self.variable = variable

    def __repr__(self):
        return f"Macro('{self.target}', '{self.variable}')"

    def json(self):
        """The JSON serialization of this object."""
        return {"macroTarget": self.target, "macroVariable": self.variable}


class CartaEncoder(json.JSONEncoder):
    """A custom encoder to JSON which correctly serialises custom objects with a ``json`` method, and numpy arrays."""

    def default(self, obj):
        """ This method is overridden from the parent class and performs the substitution."""
        if hasattr(obj, "json") and callable(obj.json):
            return obj.json()
        if type(obj).__module__ == "numpy" and type(obj).__name__ == "ndarray":
            # The condition is a workaround to avoid importing numpy
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


def cached(func):
    """A decorator which transparently caches the return value of the decorated method on the parent object.

    This should only be used on methods with return values which are not expected to change for the lifetime of the object.
    """
    @functools.wraps(func)
    def newfunc(self, *args):
        if not hasattr(self, "_cache"):
            self._cache = {}

        if func.__name__ not in self._cache:
            self._cache[func.__name__] = func(self, *args)

        return self._cache[func.__name__]

    if newfunc.__doc__ is not None:
        newfunc.__doc__ = re.sub(r"($|\n)", r" This value is transparently cached on the parent object.\1", newfunc.__doc__, 1)

    return newfunc


def split_action_path(path):
    """Extracts a path to a frontend object store and an action from a combined path.
    """
    parts = path.split('.')
    return '.'.join(parts[:-1]), parts[-1]


class SizeUnit:
    """Parses angular or pixel sizes."""
    NORMALIZED_UNIT = {
        "arcmin": "'",
        "arcsec": '"',
        "deg": "deg",
        "degree": "deg",
        "degrees": "deg",
        "px": "px",
        "pix": "px",
        "pixel": "px",
        "pixels": "px",
        "": '"',
        '"': "",
        "'": "'",
    }

    SYMBOL_UNITS = {"", "'", '"'}
    WORD_UNITS = NORMALIZED_UNIT.keys() - SYMBOL_UNITS

    SYMBOL_UNIT_REGEX = rf"^(\d+(?:\.\d+)?)({'|'.join(SYMBOL_UNITS)})$"
    WORD_UNIT_REGEX = rf"^(\d+(?:\.\d+)?)\s*({'|'.join(WORD_UNITS)})$"

    @classmethod
    def normalized(cls, size):
        try:
            size = float(size)
            return str(size), "deg"  # number or numeric string with no units = degrees
        except ValueError:
            m = re.match(cls.WORD_UNIT_REGEX, size, re.IGNORECASE)
            if m is None:
                m = re.match(cls.SYMBOL_UNIT_REGEX, size, re.IGNORECASE)
                if m is None:
                    raise ValueError(f"{repr(size)} is not in a recognized size format.")
            value, unit = m.groups()
            unit = cls.NORMALIZED_UNIT[unit]
            return value, unit  # Any other allowed unit


class CoordinateUnit:
    """Parses image or world coordinates."""

    X = "X"
    Y = "Y"

    PIXEL_UNITS = {k for k, v in SizeUnit.NORMALIZED_UNIT.items() if v == "px"}
    PIXEL_UNIT_REGEX = rf"^(\d+(?:\.\d+)?)\s*({'|'.join(PIXEL_UNITS)})$"
    HMS_COLON_REGEX = r"^-?\d{0,2}:\d{0,2}:(\d{1,2}(\.\d+)?)?$"
    HMS_LETTER_REGEX = r"^(-?\d{0,2})h(\d{0,2})m(\d{1,2}(?:\.\d+)?s)?$"
    DMS_COLON_REGEX = r"^-?\d*:\d{0,2}:(\d{1,2}(\.\d+)?)?$"
    DMS_LETTER_REGEX = r"^(-?\d*)d(\d{0,2})m(\d{1,2}(?:\.\d+)?s)?$"
    DECIMAL_REGEX = r"^-?\d+(\.\d+)?$"  # Unused here, but used in validation

    @classmethod
    def normalized(cls, coord, xy):
        if xy == cls.X:
            HMS_DMS_COLON_REGEX = cls.HMS_COLON_REGEX
            HMS_DMS_LETTER_REGEX = cls.HMS_LETTER_REGEX
        elif xy == cls.Y:
            HMS_DMS_COLON_REGEX = cls.DMS_COLON_REGEX
            HMS_DMS_LETTER_REGEX = cls.DMS_LETTER_REGEX
        else:
            raise ValueError(f"Invalid coordinate type {xy}.")
        try:
            coord = float(coord)
            return str(coord), "d"  # number or numeric string with no units = degrees
        except ValueError:
            m = re.match(cls.PIXEL_UNIT_REGEX, coord, re.IGNORECASE)
            if m is not None:
                return m.group(1), "px"  # pixels
            m = re.match(HMS_DMS_COLON_REGEX, coord, re.IGNORECASE)
            if m is not None:
                return coord, "hms" if xy == cls.X else "dms"  # H:M:S or D:M:S
            m = re.match(HMS_DMS_LETTER_REGEX, coord, re.IGNORECASE)
            if m is not None:
                HD, M, S = m.groups()
                return f"{HD}:{M}:{S}", "hms" if xy == cls.X else "dms"  # H:M:S or D:M:S
            else:
                raise ValueError(f"{repr(coord)} is not in a recognized {xy} coordinate format.")

    @classmethod
    def normalized_x(cls, coord):
        return cls.normalized(coord, cls.X)

    @classmethod
    def normalized_y(cls, coord):
        return cls.normalized(coord, cls.Y)
