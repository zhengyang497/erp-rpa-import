from types import SimpleNamespace

from import_dialog import _template_import_band_box, _template_import_click_points
from ocr_util import OcrHit, click_point_for_needle


def test_merged_toolbar_clicks_rightmost_template_import():
    text = "期初数据导入新增价格指数数据导入模板下载模板导入"
    hit = OcrHit(text=text, conf=0.99, left=10, top=10, right=410, bottom=30)
    x, y = click_point_for_needle(hit, "模板导入")
    # 24 字里「模板导入」从第 20 字起，点要落在右端那一颗按钮上，不能点整行中心。
    assert x >= 10 + int(400 * (20 / 24))
    assert x <= 410
    assert abs(y - 20) <= 1
    assert x > (10 + 410) // 2


def test_exact_hit_uses_center():
    hit = OcrHit(text="模板导入", conf=0.99, left=100, top=10, right=180, bottom=30)
    assert click_point_for_needle(hit, "模板导入") == (140, 20)


def test_template_import_band_reaches_toolbar_below_filter_form():
    fr = SimpleNamespace(left=399, top=166, right=1839, bottom=984)
    box = _template_import_band_box(fr, named=None)
    # 实测按钮相对窗口 y≈242；旧带 top+230 会裁掉。
    assert box[1] == fr.top + 70
    assert box[3] - fr.top >= 400
    assert box[2] - box[0] <= 1000


def test_template_import_click_points_split_merged_ocr():
    text = "期初数据导入新增价格指数数据导入模板下载模板导入"
    hit = OcrHit(text=text, conf=0.99, left=20, top=160, right=400, bottom=184)
    band = (399, 236, 1379, 586)
    pts = _template_import_click_points([hit], band)
    assert pts
    x, y = pts[0]
    assert x > band[0] + (20 + 400) // 2
    assert y == band[1] + 172
