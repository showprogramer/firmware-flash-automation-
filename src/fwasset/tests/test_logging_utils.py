from fwasset.core.logging_utils import FileLogger
from fwasset.core.settings import APP_LOG_PATH


def test_file_logger_writes_info_and_error(tmp_path):
    log_path = tmp_path / "logs" / "fwasset.app.log"
    logger = FileLogger(log_path)

    logger.log("hello")
    logger.exception("worker failed", "trace line 1\ntrace line 2")

    content = log_path.read_text(encoding="utf-8")

    assert "[INFO] hello" in content
    assert "[ERROR] worker failed" in content
    assert "[ERROR] trace line 1" in content
    assert "[ERROR] trace line 2" in content


def test_file_logger_defaults_to_runtime_log_path():
    logger = FileLogger()

    assert logger.path == APP_LOG_PATH
