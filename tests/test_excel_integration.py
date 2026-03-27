from pathlib import Path

from handcontrol.core.excel_ops import load_excel_row, read_all_excel_rows
from handcontrol.core.services.excel_service import merge_backup_records, write_record


def test_write_record_end_to_end_with_real_excel_file(tmp_path: Path):
    excel = tmp_path / "records.xlsx"
    rom = tmp_path / "A.ROM"
    rom.write_bytes(b"rom")

    result = write_record(
        excel_path=str(excel),
        sheet_name="Sheet1",
        model="L36",
        version="V1.2.3",
        remark="测试通过",
        rom_path=str(rom),
        logo="品牌A",
        language="中、英",
        salesman="张三",
        attachment="定制",
        log_fn=lambda _: None,
    )

    assert result["ok"] is True
    row = load_excel_row(str(excel), "Sheet1", "L36", "V1.2.3")
    assert row == {
        "logo": "品牌A",
        "salesman": "张三",
        "language": "中、英",
        "attachment": "定制",
        "remark": "测试通过",
    }


def test_merge_backup_records_end_to_end_with_real_excel_files(tmp_path: Path):
    main_excel = tmp_path / "records.xlsx"
    backup_excel = tmp_path / "records_刷机记录_待导入.xlsx"

    write_record(
        excel_path=str(main_excel),
        sheet_name="Sheet1",
        model="L36",
        version="V1.0.0",
        remark="待确认",
        rom_path="",
        log_fn=lambda _: None,
    )
    write_record(
        excel_path=str(backup_excel),
        sheet_name="Sheet1",
        model="L50S",
        version="V2.0.0",
        remark="测试通过",
        rom_path="",
        logo="品牌B",
        attachment="可通用",
        log_fn=lambda _: None,
    )

    result = merge_backup_records(
        excel_path=str(main_excel),
        backup_excel_path=str(backup_excel),
        sheet_name="Sheet1",
        log_fn=lambda _: None,
    )

    assert result["ok"] is True
    rows = read_all_excel_rows(str(main_excel), "Sheet1")
    assert len(rows) == 2
    assert rows[1][1] == "L50S"
    assert rows[1][2] == "品牌B"
    assert rows[1][7] == "可通用"
    assert backup_excel.exists() is False
