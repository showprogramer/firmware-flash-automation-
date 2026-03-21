from app import App


class FakePreview:
    def __init__(self):
        self._items = {}
        self._order = []
        self._idx = 0

    def insert(self, _parent, _where, values=None, tags=()):
        self._idx += 1
        item_id = f"i{self._idx}"
        self._items[item_id] = {"values": list(values or []), "tags": tuple(tags)}
        self._order.append(item_id)
        return item_id

    def item(self, item_id, values=None, tags=None):
        if values is not None:
            self._items[item_id]["values"] = list(values)
        if tags is not None:
            self._items[item_id]["tags"] = tuple(tags)
        return self._items[item_id]

    def get_children(self):
        return list(self._order)

    def delete(self, item_id):
        self._order = [x for x in self._order if x != item_id]
        self._items.pop(item_id, None)


def _build_app_stub():
    app = App.__new__(App)
    app.preview = FakePreview()
    app._preview_rows = []
    app._preview_by_key = {}
    app._preview_item_by_key = {}
    return app


def test_upsert_preview_row_insert_then_update():
    app = _build_app_stub()

    app._upsert_preview_row(
        {
            "model": "L36",
            "version": "V1.2.3",
            "logo": "品牌A",
            "salesman": "张三",
            "language": "中、英",
            "date": "2026.03.21",
            "remark": "待确认",
        }
    )

    assert len(app.preview.get_children()) == 1
    key = app._preview_key("L36", "V1.2.3")
    item_id = app._preview_item_by_key[key]
    assert app.preview.item(item_id)["values"][2] == "品牌A"

    app._upsert_preview_row(
        {
            "model": "l36",
            "version": "v1.2.3",
            "logo": "品牌B",
            "salesman": "李四",
            "language": "英文",
            "date": "2026.03.22",
            "remark": "测试通过",
        }
    )

    assert len(app.preview.get_children()) == 1
    item = app.preview.item(item_id)
    assert item["values"][2] == "品牌B"
    assert item["values"][3] == "李四"
    assert item["values"][4] == "英文"
    assert item["values"][7] == "测试通过"
    assert item["tags"] == ("测试通过",)


def test_row_to_preview_dict_maps_excel_columns():
    app = _build_app_stub()

    row = ["1", "L50S", "logo", "sale", "lang", "V2.0.0", "2026.03.21", "", "待确认"]
    parsed = app._row_to_preview_dict(row)

    assert parsed == {
        "serial": "1",
        "model": "L50S",
        "logo": "logo",
        "salesman": "sale",
        "language": "lang",
        "version": "V2.0.0",
        "date": "2026.03.21",
        "remark": "待确认",
    }
