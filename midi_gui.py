
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox,
    QProgressBar, QPlainTextEdit, QGroupBox,
    QFormLayout
)

from PySide6.QtCore import Qt
from stress_test import StressTest
from midi_engine import MidiEngine
from latency_graph import LatencyGraph
from burst_test import BurstTest


class MidiWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("USB-MIDI Tester 3.2")
        self.resize(900, 700)

        self.worker = None

        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)

        title = QLabel("USB-MIDI TESTER 3.2")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size:24px;font-weight:bold;padding:15px;"
        )
        layout.addWidget(title)

        ports = QGroupBox("MIDI PORT CONFIGURATION")
        port_layout = QFormLayout(ports)

        self.input_combo = QComboBox()
        self.output_combo = QComboBox()

        port_layout.addRow("MIDI INPUT:", self.input_combo)
        port_layout.addRow("MIDI OUTPUT:", self.output_combo)

        self.refresh_button = QPushButton("Refresh ports")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_layout.addRow(self.refresh_button)

        layout.addWidget(ports)

        settings = QGroupBox("TEST SETTINGS")
        settings_layout = QFormLayout(settings)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(
            "Functional test", "functional"
        )
        self.mode_combo.addItem(
            "SysEx stress test", "stress"
        )
        self.mode_combo.addItem(
            "Full test", "full"
        )

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 28800)
        self.duration_spin.setValue(60)
        self.duration_spin.setSuffix(" seconds")

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(100, 5000)
        self.timeout_spin.setValue(500)
        self.timeout_spin.setSuffix(" ms")

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 1000)
        self.delay_spin.setValue(15)
        self.delay_spin.setSuffix(" ms")

        settings_layout.addRow("Test mode:", self.mode_combo)
        settings_layout.addRow("Stress duration:", self.duration_spin)
        settings_layout.addRow("Response timeout:", self.timeout_spin)
        settings_layout.addRow("Send interval:", self.delay_spin)

        layout.addWidget(settings)

        controls = QHBoxLayout()

        self.start_button = QPushButton("START TEST")
        self.stop_button = QPushButton("STOP")
        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_test)
        self.stop_button.clicked.connect(self.stop_test)

        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        
        self.burst_button = QPushButton("START BURST TEST")
        self.burst_button.clicked.connect(self.start_burst)

        controls.addWidget(self.burst_button)

        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.status = QLabel("Ready")
        layout.addWidget(self.status)

        self.stats = QLabel(
            "Sent: 0 | PASS: 0 | Lost: 0 | "
            "Mismatch: 0 | Duplicates: 0"
        )
        layout.addWidget(self.stats)
        
        layout.addWidget(QLabel("ROUND TRIP LATENCY"))

        self.latency_graph = LatencyGraph()
        layout.addWidget(self.latency_graph)

        self.monitor = QPlainTextEdit()
        self.monitor.setReadOnly(True)
        self.monitor.setMaximumBlockCount(3000)

        layout.addWidget(QLabel("MIDI EVENT MONITOR"))
        layout.addWidget(self.monitor)

        self.refresh_ports()

    def refresh_ports(self):
        self.input_combo.clear()
        self.output_combo.clear()

        try:
            inputs = MidiEngine.input_ports()
            outputs = MidiEngine.output_ports()

            self.input_combo.addItems(inputs)
            self.output_combo.addItems(outputs)

            self.status.setText(
                f"Found {len(inputs)} IN and "
                f"{len(outputs)} OUT ports"
            )

        except Exception as exc:
            self.status.setText(f"Port error: {exc}")

    def start_test(self):
        self.latency_graph.clear()
        input_port = self.input_combo.currentText()
        output_port = self.output_combo.currentText()

        if not input_port or not output_port:
            self.status.setText("Select MIDI IN and OUT!")
            return

        self.monitor.clear()
        self.progress.setValue(0)

        mode = self.mode_combo.currentData()

        self.worker = StressTest(
            input_port=input_port,
            output_port=output_port,
            mode=mode,
            duration=self.duration_spin.value(),
            timeout=self.timeout_spin.value() / 1000,
            delay=self.delay_spin.value() / 1000
        )

        self.worker.progress.connect(self.update_progress)
        self.worker.event.connect(self.update_event)
        self.worker.completed.connect(self.test_completed)
        self.worker.error.connect(self.test_error)

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.refresh_button.setEnabled(False)

        self.status.setText("Test running...")

        self.worker.start()

    def stop_test(self):
        if self.worker:
            self.worker.stop()
            self.status.setText("Stopping test...")
            
    
    def start_burst(self):

        input_port = self.input_combo.currentText()
        output_port = self.output_combo.currentText()

        if not input_port or not output_port:
            self.status.setText("Select MIDI IN and OUT!")
            return

        self.monitor.clear()
        self.latency_graph.clear()
        self.progress.setValue(0)

        self.worker = BurstTest(
            input_port=input_port,
            output_port=output_port,
            packet_count=500,
            interval_ms=5,
            timeout=3.0
        )

        self.worker.progress.connect(self.update_progress)
        self.worker.event.connect(self.update_event)
        self.worker.completed.connect(self.test_completed)
        self.worker.error.connect(self.test_error)

        self.start_button.setEnabled(False)
        self.burst_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.refresh_button.setEnabled(False)

        self.status.setText("Burst stress test running...")

        self.worker.start()


    def update_progress(self, current, total):
        if total > 0:
            self.progress.setValue(
                int(current / total * 100)
            )

    
    def update_event(self, record):

        latency = record.get("latency")

        if latency is not None:
            self.latency_graph.add_value(latency)

        verification = record.get(
            "byte_verification", {}
        )

        name = record.get("test", "MIDI")

        status = record.get("status", "UNKNOWN")

        self.monitor.appendPlainText(
            f"{name} | {status} | "
            f"Latency: {latency if latency is not None else '-'} ms"
        )

        if verification:

            self.monitor.appendPlainText(
                f"TX: {verification.get('expected_hex', '')}"
            )

            self.monitor.appendPlainText(
                f"RX: {verification.get('received_hex', '')}"
            )

            for diff in verification.get("differences", []):

                self.monitor.appendPlainText(
                    f"BYTE ERROR at position "
                    f"{diff['position']}: "
                    f"TX={diff['expected_hex']} "
                    f"RX={diff['received_hex']}"
                )



    def test_completed(self, result):
        self.progress.setValue(100)
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.refresh_button.setEnabled(True)

        self.stats.setText(
            f"Sent: {result['sent']} | "
            f"PASS: {result['passed']} | "
            f"Lost: {result['lost']} | "
            f"Mismatch: {result['mismatch']} | "
            f"Duplicates: {result['duplicates']}"
        )

        self.monitor.appendPlainText("\n===== FINAL RESULT =====")

        for key, value in result.items():
            self.monitor.appendPlainText(
                f"{key}: {value}"
            )

        self.status.setText("Test completed")
        self.burst_button.setEnabled(True)

    def test_error(self, message):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.refresh_button.setEnabled(True)

        self.status.setText("Test error: " + message)
        self.monitor.appendPlainText("ERROR: " + message)
        self.burst_button.setEnabled(True)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)

        event.accept()


def main():
    app = QApplication(sys.argv)

    window = MidiWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
