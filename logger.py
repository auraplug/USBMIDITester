
import csv
import json

from pathlib import Path
from datetime import datetime
from html import escape


class TestLogger:

    def __init__(self, input_port="", output_port=""):

        self.directory = Path("reports")
        self.directory.mkdir(exist_ok=True)

        self.timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        
        self.app_version = "3.2"
        self.input_port = input_port
        self.output_port = output_port

        self.csv_path = (
            self.directory / f"midi_events_{self.timestamp}.csv"
        )

        self.json_path = (
            self.directory / f"midi_report_{self.timestamp}.json"
        )

        self.html_path = (
            self.directory / f"midi_report_{self.timestamp}.html"
        )

        self.file = open(
            self.csv_path,
            "w",
            newline="",
            encoding="utf-8-sig"
        )

        self.writer = csv.writer(self.file)

        # CSV fejléc - 11 oszlop
        self.writer.writerow([
            "Timestamp",
            "Test",
            "Expected",
            "Received",
            "Status",
            "Expected_Length",
            "Received_Length",
            "Byte_Errors",
            "Byte_Differences",
            "Latency_ms",
            "Duplicates"
        ])

        self.closed = False

    def write(self, record):

        if self.closed or self.file.closed:
            return

        verification = record.get(
            "byte_verification", {}
        )

        differences = verification.get(
            "differences", []
        )

        self.writer.writerow([
            datetime.now().isoformat(
                timespec="milliseconds"
            ),
            record.get("test", ""),
            verification.get(
                "expected_hex",
                record.get("expected", "")
            ),
            verification.get("received_hex", ""),
            record.get("status", ""),
            verification.get("expected_length", ""),
            verification.get("received_length", ""),
            verification.get("byte_errors", 0),
            json.dumps(differences, ensure_ascii=False),
            record.get("latency"),
            record.get("duplicates", 0)
        ])

        self.file.flush()

    def close(self, summary=None):

        # Dupla lezárás elleni védelem
        if self.closed:
            return

        self.closed = True

        if summary is None:
            summary = {}

        # CSV lezárása
        if self.file is not None and not self.file.closed:

            self.file.flush()
            self.file.close()

        # JSON riport
        report = {
            "application": "USB-MIDI Tester",
            "version": self.app_version,
            "created": datetime.now().isoformat(),

            "midi_interface": {
                "input": self.input_port,
                "output": self.output_port
            },

            "statistics": summary
        }

        self.json_path.write_text(
            json.dumps(
                report,
                indent=4,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        # HTML riport adatok
        rows = "".join(
            f"<tr><td>{escape(str(k))}</td>"
            f"<td>{escape(str(v))}</td></tr>"
            for k, v in summary.items()
        )

        html = f"""
        <!DOCTYPE html>
        <html lang="hu">
        <head>
        <meta charset="UTF-8">
        <title>USB-MIDI Tester Report</title>

        <style>
        body {{
            font-family: Arial, sans-serif;
            background: #151923;
            color: #eeeeee;
            padding: 30px;
        }}

        table {{
            border-collapse: collapse;
            width: 600px;
            max-width: 100%;
        }}

        td, th {{
            padding: 12px;
            border-bottom: 1px solid #444;
            text-align: left;
        }}

        th {{
            background: #29354a;
        }}
        </style>

        </head>

        <body>

        <h1>USB-MIDI Tester {self.app_version}</h1>

        <p>Test report: {datetime.now()}</p>

        <h2>MIDI Interface</h2>

        <p>
        <strong>MIDI IN:</strong>
        {escape(self.input_port)}
        </p>

        <p>
        <strong>MIDI OUT:</strong>
        {escape(self.output_port)}
        </p>

        <table>

        <tr>
            <th>Parameter</th>
            <th>Result</th>
        </tr>

        {rows}

        </table>

        </body>
        </html>
        """

        self.html_path.write_text(
            html,
            encoding="utf-8"
        )
