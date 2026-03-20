from pathlib import Path

# Default paths and worksheet structure
DEFAULT_ROOT = r"D:\按摩椅相关文件汇总\YJ-按摩椅家用，商用程序汇总（之前没整理的）"
DEFAULT_EXCEL = str(Path(__file__).resolve().parent.parent / "data" / "handcontrol_ui_template.xlsx")
EXCEL_SHEET = "Sheet1"
EXCEL_HEADER_ROW = 2  # Row 2 is header, row 1 is title

# USB cleanup defaults
JUNK_EXTENSIONS = {".usu", ".tmp", ".bak"}
JUNK_FILENAMES = {"autorun.inf"}
