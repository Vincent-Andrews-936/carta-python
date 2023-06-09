import types
import pytest

from carta.session import Session
from carta.image import Image
from carta.util import CartaValidationFailed
from carta.constants import NumberFormat as NF, CoordinateSystem

# FIXTURES


@pytest.fixture
def session():
    """Return a session object.

    The session's protocol is set to None, so any tests that use this must also mock the session's call_action and/or higher-level functions which call it.
    """
    return Session(0, None)


@pytest.fixture
def image(session):
    """Return an image object which uses the session fixture.
    """
    return Image(session, 0, "")


@pytest.fixture
def mock_get_value(image, mocker):
    """Return a mock for image's get_value."""
    return mocker.patch.object(image, "get_value")


@pytest.fixture
def mock_call_action(image, mocker):
    """Return a mock for image's call_action."""
    return mocker.patch.object(image, "call_action")


@pytest.fixture
def mock_session_call_action(session, mocker):
    """Return a mock for session's call_action."""
    return mocker.patch.object(session, "call_action")


@pytest.fixture
def mock_property(mocker):
    """Return a helper function to mock the value of a decorated image property using a simple syntax."""
    def func(property_name, mock_value):
        mocker.patch(f"carta.image.Image.{property_name}", new_callable=mocker.PropertyMock, return_value=mock_value)
    return func


@pytest.fixture
def mock_method(image, mocker):
    """Return a helper function to mock the return value(s) of an image method using a simple syntax."""
    def func(method_name, return_values):
        mocker.patch.object(image, method_name, side_effect=return_values)
    return func


@pytest.fixture
def mock_session_method(session, mocker):
    """Return a helper function to mock the return value(s) of a session method using a simple syntax."""
    def func(method_name, return_values):
        mocker.patch.object(session, method_name, side_effect=return_values)
    return func

# TESTS

# DOCSTRINGS


def test_image_class_has_docstring():
    assert Image.__doc__ is not None


def find_members(*classes, member_type=types.FunctionType):
    for clazz in classes:
        for name in dir(clazz):
            if not name.startswith('__') and isinstance(getattr(clazz, name), member_type):
                yield getattr(clazz, name)


@pytest.mark.parametrize("member", find_members(Image))
def test_image_methods_have_docstrings(member):
    assert member.__doc__ is not None


@pytest.mark.parametrize("member", find_members(Image, member_type=types.MethodType))
def test_image_classmethods_have_docstrings(member):
    assert member.__doc__ is not None


@pytest.mark.parametrize("member", [m.fget for m in find_members(Image, member_type=property)])
def test_image_properties_have_docstrings(member):
    assert member.__doc__ is not None

# SIMPLE PROPERTIES TODO to be completed.


@pytest.mark.parametrize("property_name,expected_path", [
    ("directory", "frameInfo.directory"),
    ("width", "frameInfo.fileInfoExtended.width"),
])
def test_simple_properties(image, property_name, expected_path, mock_get_value):
    getattr(image, property_name)
    mock_get_value.assert_called_with(expected_path)

# TODO tests for all existing functions to be filled in


def test_make_active(image, mock_session_call_action):
    image.make_active()
    mock_session_call_action.assert_called_with("setActiveFrameById", 0)


@pytest.mark.parametrize("channel", [0, 10, 19])
def test_set_channel_valid(image, channel, mock_call_action, mock_property):
    mock_property("depth", 20)

    image.set_channel(channel)
    mock_call_action.assert_called_with("setChannels", channel, image.macro("", "requiredStokes"), True)


@pytest.mark.parametrize("channel,error_contains", [
    (20, "must be smaller"),
    (1.5, "not an increment of 1"),
    (-3, "must be greater or equal"),
])
def test_set_channel_invalid(image, channel, error_contains, mock_property):
    mock_property("depth", 20)

    with pytest.raises(CartaValidationFailed) as e:
        image.set_channel(channel)
    assert error_contains in str(e.value)


@pytest.mark.parametrize("x", [0, 10, 19])
@pytest.mark.parametrize("y", [0, 10, 19])
def test_set_center_valid_pixels(image, mock_property, mock_call_action, x, y):
    mock_property("width", 20)
    mock_property("height", 20)

    image.set_center(f"{x}px", f"{y}px")
    mock_call_action.assert_called_with("setCenter", float(x), float(y))


@pytest.mark.parametrize("x,y,x_fmt,y_fmt,x_norm,y_norm", [
    ("123", "123", NF.DEGREES, NF.DEGREES, "123", "123"),
    (123, 123, NF.DEGREES, NF.DEGREES, "123", "123"),
    ("123deg", "123 deg", NF.DEGREES, NF.DEGREES, "123", "123"),
    ("12:34:56.789", "12:34:56.789", NF.HMS, NF.DMS, "12:34:56.789", "12:34:56.789"),
    ("12h34m56.789s", "12d34m56.789s", NF.HMS, NF.DMS, "12:34:56.789", "12:34:56.789"),
])
def test_set_center_valid_wcs(image, mock_property, mock_session_method, mock_call_action, x, y, x_fmt, y_fmt, x_norm, y_norm):
    mock_property("valid_wcs", True)
    mock_session_method("number_format", [(x_fmt, y_fmt, None)])

    image.set_center(x, y)
    mock_call_action.assert_called_with("setCenterWcs", x_norm, y_norm)


def test_set_center_valid_change_system(image, mock_property, mock_session_method, mock_call_action, mock_session_call_action):
    mock_property("valid_wcs", True)
    mock_session_method("number_format", [(NF.DEGREES, NF.DEGREES, None)])

    image.set_center("123", "123", CoordinateSystem.GALACTIC)

    # We're not testing if this system has the correct format; just that the function is called
    mock_session_call_action.assert_called_with("overlayStore.global.setSystem", CoordinateSystem.GALACTIC)
    mock_call_action.assert_called_with("setCenterWcs", "123", "123")


@pytest.mark.parametrize("x,y,wcs,x_fmt,y_fmt,error_contains", [
    ("abc", "def", True, NF.DEGREES, NF.DEGREES, "Invalid function parameter"),
    ("123", "123", False, NF.DEGREES, NF.DEGREES, "does not contain valid WCS information"),
    ("123", "123", True, NF.HMS, NF.DMS, "does not match expected format"),
    ("123", "123", True, NF.DEGREES, NF.DMS, "does not match expected format"),
    ("123px", "123", True, NF.DEGREES, NF.DEGREES, "Cannot mix image and world coordinates"),
    ("123", "123px", True, NF.DEGREES, NF.DEGREES, "Cannot mix image and world coordinates"),
    ("123px", "2000px", True, NF.DEGREES, NF.DEGREES, "outside the bounds of the image"),
    ("2000px", "123px", True, NF.DEGREES, NF.DEGREES, "outside the bounds of the image"),
])
def test_set_center_invalid(image, mock_property, mock_session_method, mock_call_action, x, y, wcs, x_fmt, y_fmt, error_contains):
    mock_property("width", 200)
    mock_property("height", 200)
    mock_property("valid_wcs", wcs)
    mock_session_method("number_format", [(x_fmt, y_fmt, None)])

    with pytest.raises(Exception) as e:
        image.set_center(x, y)
    assert error_contains in str(e.value)


@pytest.mark.parametrize("dim", ["x", "y"])
@pytest.mark.parametrize("val,action,norm", [
    ("123px", "zoomToSize{0}", 123.0),
    ("123arcsec", "zoomToSize{0}Wcs", "123\""),
    ("123\"", "zoomToSize{0}Wcs", "123\""),
    ("123", "zoomToSize{0}Wcs", "123\""),
    ("123arcmin", "zoomToSize{0}Wcs", "123'"),
    ("123deg", "zoomToSize{0}Wcs", "123deg"),
    ("123 deg", "zoomToSize{0}Wcs", "123deg"),
])
def test_zoom_to_size(image, mock_property, mock_call_action, dim, val, action, norm):
    mock_property("valid_wcs", True)
    getattr(image, f"zoom_to_size_{dim}")(val)
    mock_call_action.assert_called_with(action.format(dim.upper()), norm)


@pytest.mark.parametrize("dim", ["x", "y"])
@pytest.mark.parametrize("val,wcs,error_contains", [
    ("abc", True, "Invalid function parameter"),
    ("123arcsec", False, "does not contain valid WCS information"),
])
def test_zoom_to_size_invalid(image, mock_property, dim, val, wcs, error_contains):
    mock_property("valid_wcs", wcs)
    with pytest.raises(Exception) as e:
        getattr(image, f"zoom_to_size_{dim}")(val)
    assert error_contains in str(e.value)
