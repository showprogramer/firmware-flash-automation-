from core.sort_config import SortKey, apply_sort


def test_apply_sort_by_default_path_order():
    folders = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/x/aaa"},
        {"model": "L50S", "version": "V2.0.0", "path": "D:/a/zzz"},
    ]

    result = apply_sort(folders, sort_key=SortKey.PATH, ascending=True)

    assert [item["path"] for item in result] == ["D:/a/zzz", "D:/x/aaa"]


def test_apply_sort_by_model_natural_order():
    folders = [
        {"model": "L50S", "version": "V1.0.0", "path": "D:/b"},
        {"model": "L36", "version": "V1.0.0", "path": "D:/a"},
        {"model": "L100", "version": "V1.0.0", "path": "D:/c"},
    ]

    result = apply_sort(folders, sort_key=SortKey.MODEL, ascending=True)

    assert [item["model"] for item in result] == ["L36", "L50S", "L100"]


def test_apply_sort_by_version_numeric_order():
    folders = [
        {"model": "L36", "version": "V10.0.0", "path": "D:/a"},
        {"model": "L36", "version": "V2.0.0", "path": "D:/b"},
        {"model": "L36", "version": "V1.9", "path": "D:/c"},
    ]

    result = apply_sort(folders, sort_key=SortKey.VERSION, ascending=True)

    assert [item["version"] for item in result] == ["V1.9", "V2.0.0", "V10.0.0"]


def test_apply_sort_by_status_with_status_map():
    folders = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a"},
        {"model": "L50S", "version": "V2.0.0", "path": "D:/b"},
        {"model": "L66", "version": "V3.0.0", "path": "D:/c"},
    ]
    status_map = {
        ("L36", "V1.0.0"): "测试通过",
        ("L50S", "V2.0.0"): "待确认",
    }

    result = apply_sort(folders, sort_key=SortKey.STATUS, ascending=True, status_map=status_map)

    assert [(item["model"], item["version"]) for item in result] == [
        ("L50S", "V2.0.0"),
        ("L36", "V1.0.0"),
        ("L66", "V3.0.0"),
    ]


def test_apply_sort_descending():
    folders = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a"},
        {"model": "L50S", "version": "V2.0.0", "path": "D:/b"},
    ]

    result = apply_sort(folders, sort_key=SortKey.MODEL, ascending=False)

    assert [item["model"] for item in result] == ["L50S", "L36"]
