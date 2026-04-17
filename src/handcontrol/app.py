import os

from handcontrol.ui.handcontrol_panel import HandcontrolPanel as App
from handcontrol.ui import shell
from handcontrol.ui.shell import UnifiedFlashPlatform

# Legacy imports for tests
from handcontrol.core.diagnostics import build_diagnostic_bundle
from handcontrol.core.services.at_command_service import apply_baudrate_command
from handcontrol.core.services.excel_service import delete_record, merge_backup_records, update_record_fields, write_record
from handcontrol.core.services.flash_service import run_one_click
from handcontrol.core.services.music_flash_service import run_music_flash
from handcontrol.core.services.scan_service import build_scan_result
from handcontrol.core.services.serial_service import connect_port, disconnect_port, scan_serial_ports
from handcontrol.core.services.usb_repair_service import diagnose_drive, repair_drive
from handcontrol.core.usb_ops import get_usb_drives


def main():
    shell.main()


if __name__ == "__main__":
    main()
