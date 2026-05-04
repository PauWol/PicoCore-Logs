
import ast
import subprocess
import time
import tempfile
import pathlib
from typing import Callable, Optional,Literal

import serial.tools.list_ports

from log_conv import parse_log_file,convert

ProgressCallback = Optional[Callable[[str, dict], None]]

class Events:
    START = "start"
    FILES_FOUND = "files_found"
    DOWNLOAD_START = "download_start"
    DOWNLOAD_DONE = "download_done"
    CONVERT_START = "convert_start"
    CONVERT_DONE = "convert_done"
    DONE = "done"
    DELETE_START = "delete_start"
    DELETE_DONE = "delete_done"

class BoardPortNotSet(Exception):
    def __init__(self, message=None):
        if message is None:
            message = "Board port is not set. Use 'set_port(port)' first. " \
                    "To find the desired port use 'list_all_ports()'."
        super().__init__(message)


_LOG_FILE_FORMAT = "logs.bin"

LEVEL_NAMES = {
    1: "FATAL",
    2: "ERROR",
    3: "WARN",
    4: "INFO",
    5: "DEBUG",
    6: "TRACE",
}
LEVEL_NAMES_REV = {v: k for k, v in LEVEL_NAMES.items()}
VALID_LEVELS = set(LEVEL_NAMES)


class Board():
    def __init__(self, port = None):
        self.port = port

    def _board_port_guard(self):
        if not self.port:
            raise BoardPortNotSet()

    
    def set_port(self,port):
        self.port = port

    @staticmethod
    def list_all_ports(filter: bool = True):
        """
        Generate available serial ports.

        Iterates over all detected serial ports on the system and yields
        each port object. Optionally filters out ports that do not provide
        valid hardware identification (VID, PID, or HWID).

        :param filter: If True, skips ports without valid VID/PID or with
                    missing hardware ID ("n/a"). Defaults to True.
        :type filter: bool

        :yields: Serial port information objects as returned by
                `serial.tools.list_ports.comports()`
        :rtype: Iterator[serial.tools.list_ports_common.ListPortInfo]
        """
        for port in serial.tools.list_ports.comports():
            if (not port.vid and not port.pid or port.hwid == "n/a") and filter:
                continue

            yield port

    def interrupt_board(self):
        self._board_port_guard()

        with serial.Serial(self.port, 115200, timeout=1) as ser:
            time.sleep(0.5)

            # clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # interrupt
            ser.write(b"\r\n\x03\x03")
            ser.flush()

            # give board time to return to REPL
            time.sleep(1.0)

    def list_root_fs(self):
        result = subprocess.run(
            [
                "mpremote",
                "connect", self.port,
                "exec",
                "import os; print(os.listdir('/'))"
            ],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()

        try:
            return ast.literal_eval(output)
        except Exception:
            return []
    
    def _download(self, remote_path, local_path):
        result = subprocess.run(
            [
                "mpremote",
                "connect", self.port,
                "fs", "cp",
                f":{remote_path}",
                local_path
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Download failed:\n{result.stderr}")

        return result.stdout
    

    @staticmethod
    def _downloads_dir():
        return pathlib.Path().home() / "Downloads"
    
    @staticmethod
    def _temp_dir():
        return tempfile.gettempdir()
    

    def _get_log_files(self):
        fsr = self.list_root_fs()

        for i in fsr:
            if i == _LOG_FILE_FORMAT or str(i).startswith(_LOG_FILE_FORMAT):
                yield i

    
    def download_logs(self,auto_convert: bool = False,format: Literal['text', 'csv', 'json', 'table'] = 'csv', min_level: Literal[0,1,2,3,4,5,6] = 0,callback: ProgressCallback = None):
        self._board_port_guard()

        if callback:
            callback("start", {"auto_convert": auto_convert})

        local_path = (pathlib.Path(self._temp_dir()) if auto_convert else self._downloads_dir())

        lfs = []

        files = list(self._get_log_files())

        if callback:
            callback("files_found", {"count": len(files), "files": files})

        for idx, i in enumerate(files):
            if callback:
                callback("download_start", {"file": i, "index": idx})

            self._download(i, local_path)
            lfs.append(i)

            if callback:
                callback("download_done", {"file": i, "index": idx})

        if not auto_convert:
            return local_path, lfs
        
        dwn = self._downloads_dir()

        r = []

        for idx, i in enumerate(lfs):
            if callback:
                callback("convert_start", {"file": i})

            records = parse_log_file(local_path / i, min_level)

            output_file = dwn / f"{pathlib.Path(i).stem}.{format}"
            result = convert(records, format, output_file)

            if callback:
                callback("convert_done", {"file": i, "output": str(output_file)})

            r.append(result)

        if callback:
            callback("done", {"output_dir": str(dwn)})

        return dwn,r
        
    def delete_logs(self, callback: ProgressCallback = None):
        self._board_port_guard()

        if callback:
            callback(Events.START, {"action": "delete_logs"})

        self.interrupt_board()

        files = list(self._get_log_files())

        if callback:
            callback(Events.FILES_FOUND, {"count": len(files), "files": files})

        if not files:
            if callback:
                callback(Events.DONE, {"deleted": []})
            return []

        files_str = ", ".join([f"'{f}'" for f in files])

        cmd = (
            "import os\n"
            "deleted=[]\n"
            f"files=[{files_str}]\n"
            "for f in files:\n"
            "    try:\n"
            "        os.remove(f)\n"
            "        deleted.append(f)\n"
            "    except OSError:\n"
            "        pass\n"
            "print(deleted)\n"
        )

        result = subprocess.run(
            [
                "mpremote",
                "connect", self.port,
                "exec",
                cmd
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Batch delete failed:\n{result.stderr or result.stdout}")

        try:
            deleted = ast.literal_eval(result.stdout.strip())
        except Exception:
            deleted = []

        if callback:
            for f in deleted:
                callback(Events.DOWNLOAD_DONE, {"file": f})

            callback(Events.DONE, {"deleted": deleted})

        return deleted
                    
                




        


if __name__ == '__main__':
    port = "/dev/ttyACM0"
    bord = Board(port=port)

    
    bord.interrupt_board()
    print(bord.list_root_fs())
    print(bord.delete_logs())
    print(bord.list_root_fs())