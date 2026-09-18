from types import SimpleNamespace

from menu_nav import (
    PRICE_NAV_ATTEMPTS,
    _chrome_click_coords,
    _looks_like_price_screen,
    _menu_bbox,
    _named_exists,
    _point_in_frame_content,
    _price_drop_bbox,
)


class _Rect:
    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom


class _Ctrl:
    def __init__(self, name, rect):
        self.element_info = SimpleNamespace(name=name)
        self._rect = rect

    def rectangle(self):
        return self._rect


class _Frame:
    def __init__(self, left, top, right, bottom, controls=None):
        self._r = _Rect(left, top, right, bottom)
        self._controls = controls or []

    def rectangle(self):
        return self._r

    def descendants(self):
        return self._controls


def test_chrome_click_hits_title_bar_not_document_body():
    frame = _Frame(0, 100, 1000, 800)
    x, y = _chrome_click_coords(frame)
    assert x == 500
    assert y == 108
    assert y < 100 + 40


def test_price_nav_retries_three_times():
    assert PRICE_NAV_ATTEMPTS == 3


def test_price_dropdown_fallback_bbox_is_wider_than_right_strip():
    frame = _Frame(0, 0, 1600, 900)
    right = _price_drop_bbox(frame)
    full = _menu_bbox(frame)
    assert right[0] > full[0]
    assert full[2] <= 1600


def test_menu_name_is_not_price_screen():
    frame = _Frame(
        0,
        0,
        1600,
        900,
        [_Ctrl("商品指数登记", _Rect(1200, 20, 1400, 40))],
    )
    assert not _looks_like_price_screen(frame)
    assert not _named_exists(frame, "商品指数登记", require_visible=True)


def test_visible_template_button_is_price_screen():
    frame = _Frame(
        0,
        0,
        1600,
        900,
        [_Ctrl("模板导入", _Rect(80, 90, 160, 118))],
    )
    assert _looks_like_price_screen(frame)
    assert _named_exists(frame, "模板导入", require_visible=True)


def test_offscreen_ghost_control_is_not_visible():
    frame = _Frame(
        0,
        0,
        1600,
        900,
        [_Ctrl("模板导入", _Rect(-32000, -32000, -31900, -31900))],
    )
    assert not _looks_like_price_screen(frame)
    assert _named_exists(frame, "模板导入", require_visible=False)
    assert not _point_in_frame_content(frame, _Rect(-32000, -32000, -31900, -31900))
