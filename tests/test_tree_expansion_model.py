from fwasset.ui.view_models.tree_expansion_model import TreeExpansionModel


def test_tree_expansion_model_starts_empty():
    model = TreeExpansionModel()
    assert model.expanded == set()
    assert model.is_open("series|L36") is False


def test_tree_expansion_model_mark_open_closed():
    model = TreeExpansionModel()
    model.mark_open("series|L36")
    assert model.is_open("series|L36") is True
    model.mark_closed("series|L36")
    assert model.is_open("series|L36") is False


def test_tree_expansion_model_toggle():
    model = TreeExpansionModel()
    assert model.toggle("type|D:/root/L36|mainboard") is True
    assert model.is_open("type|D:/root/L36|mainboard") is True
    assert model.toggle("type|D:/root/L36|mainboard") is False
    assert model.is_open("type|D:/root/L36|mainboard") is False


def test_tree_expansion_model_clear():
    model = TreeExpansionModel()
    model.mark_open("a")
    model.mark_open("b")
    model.clear()
    assert model.expanded == set()


def test_tree_expansion_model_mark_closed_idempotent():
    model = TreeExpansionModel()
    model.mark_closed("nonexistent")
    assert model.expanded == set()