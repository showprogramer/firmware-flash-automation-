import os


def main():
    # 双轨期开关：FWASSET_UI=qt 走 PySide6 新壳（迁移中），默认仍为 CTk。
    # 见 specs/active/TASK-20260708-pyside6-migration.md。
    if os.environ.get("FWASSET_UI", "").strip().lower() == "qt":
        from fwasset.ui_qt.workbench_window import main as qt_main

        raise SystemExit(qt_main())

    from fwasset.ui.shell import UnifiedFlashPlatform as App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
