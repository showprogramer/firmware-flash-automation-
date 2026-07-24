from fwasset.ui_common.view_models.scan_state_model import ScanStateModel


def test_scan_state_model_tracks_scan_lifecycle():
    model = ScanStateModel()

    event = model.begin()

    assert model.is_scanning
    assert model.cancel_event is event

    assert model.request_cancel()
    assert event.is_set()

    model.finish(event)

    assert not model.is_scanning
    assert model.cancel_event is None


def test_scan_state_model_keeps_new_scan_when_old_event_finishes():
    model = ScanStateModel()
    old_event = model.begin()
    model.finish(old_event)
    new_event = model.begin()

    model.finish(old_event)

    assert model.is_scanning
    assert model.cancel_event is new_event


def test_scan_state_model_rejects_second_begin():
    model = ScanStateModel()
    event = model.begin()

    assert model.begin() is event
    assert model.cancel_event is event


def test_scan_state_model_can_replace_current_event():
    model = ScanStateModel()
    event = model.begin()

    model.replace(None)

    assert model.cancel_event is None
    assert not event.is_set()


def test_scan_state_model_request_cancel_without_scan_is_false():
    model = ScanStateModel()

    assert not model.request_cancel()
