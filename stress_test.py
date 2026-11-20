
import time
import statistics
import mido

from PySide6.QtCore import QThread, Signal
from midi_engine import MidiEngine
from logger import TestLogger


def functional_messages():
    messages = []

    # Note On / Note Off
    for note in range(128):
        messages.append(mido.Message(
            "note_on", channel=0,
            note=note, velocity=100
        ))

        messages.append(mido.Message(
            "note_off", channel=0,
            note=note, velocity=0
        ))

    # Control Change
    for cc in range(128):
        messages.append(mido.Message(
            "control_change",
            channel=0,
            control=cc,
            value=(cc * 7) % 128
        ))

    # Program Change
    for program in range(128):
        messages.append(mido.Message(
            "program_change",
            channel=0,
            program=program
        ))

    # Pitch Bend
    for pitch in range(-8192, 8192, 512):
        messages.append(mido.Message(
            "pitchwheel",
            channel=0,
            pitch=pitch
        ))

    return messages


def sysex_message(sequence):
    return mido.Message(
        "sysex",
        data=[
            0x7D, 0x01,
            (sequence >> 21) & 0x7F,
            (sequence >> 14) & 0x7F,
            (sequence >> 7) & 0x7F,
            sequence & 0x7F
        ]
    )


class StressTest(QThread):

    progress = Signal(int, int)
    event = Signal(dict)
    completed = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        input_port,
        output_port,
        mode="full",
        duration=60,
        timeout=0.5,
        delay=0.015
    ):
        super().__init__()

        self.input_port = input_port
        self.output_port = output_port
        self.mode = mode
        self.duration = duration
        self.timeout = timeout
        self.delay = delay

        self.running = True
        self.engine = MidiEngine()

        self.stats = {
            "sent": 0,
            "passed": 0,
            "lost": 0,
            "mismatch": 0,
            "duplicates": 0,
            "byte_errors": 0,
            "length_errors": 0,
            "exact_matches": 0
        }

        self.latencies = []
        self.logger = None

    def stop(self):
        self.running = False
        
    
    
    def process_message(self, msg, name):

        if not self.running:
            return

        result = self.engine.send_and_wait(
            msg,
            timeout=self.timeout
        )

        self.stats["sent"] += 1
        self.stats["mismatch"] += result["mismatch"]
        self.stats["duplicates"] += result["duplicates"]

        # =====================================
        # BYTE-LEVEL VERIFICATION
        # =====================================

        verification = result.get(
            "byte_verification", {}
        )

        if verification:

            if verification.get("passed"):
                self.stats["exact_matches"] += 1

            self.stats["byte_errors"] += (
                verification.get("byte_errors", 0)
            )

            if not verification.get("length_match"):
                self.stats["length_errors"] += 1

        # =====================================
        # TEST RESULT
        # =====================================

        if result["status"] == "PASS":

            self.stats["passed"] += 1

            self.latencies.append(
                result["latency"]
            )

        else:
            self.stats["lost"] += 1

        # =====================================
        # EVENT RECORD
        # =====================================

        record = {
            "test": name,
            "expected": str(msg.bytes()),
            "status": result["status"],
            "latency": result["latency"],
            "duplicates": result["duplicates"],
            "mismatch": result["mismatch"],
            "byte_verification": verification
        }

        # CSV naplózás
        self.logger.write(record)

        # GUI esemény
        self.event.emit(record)

    def run(self):
        try:
            self.engine.open(
                self.input_port,
                self.output_port
            )

            self.logger = TestLogger(
                input_port=self.input_port,
                output_port=self.output_port
            )

            if self.mode in ("functional", "full"):
                messages = functional_messages()
                total = len(messages)

                for i, msg in enumerate(messages):
                    if not self.running:
                        break

                    self.process_message(msg, msg.type)
                    self.progress.emit(i + 1, total)

                    if self.delay:
                        time.sleep(self.delay)

            if self.mode in ("stress", "full") and self.running:
                print("SysEx stress test started")

                sequence = 0
                end = time.monotonic() + self.duration

                while self.running and time.monotonic() < end:
                    self.process_message(
                        sysex_message(sequence),
                        "SYSEX_STRESS"
                    )

                    sequence += 1

                    if sequence % 20 == 0:
                        self.progress.emit(
                            min(
                                99,
                                int(
                                    (1 - max(
                                        0,
                                        end - time.monotonic()
                                    ) / self.duration
                                    ) * 100
                                )
                            ),
                            100
                        )

                    if self.delay:
                        time.sleep(self.delay)

            self.engine.close()

            if self.logger:
                self.logger.close(self.summary())
                
            # Progressbar végleges beállítása
            if self.running:
                self.progress.emit(100, 100)

            self.completed.emit(self.summary())

        except Exception as exc:
            self.engine.close()

            if self.logger:
                self.logger.close(self.summary())

            self.error.emit(str(exc))

    def summary(self):
        values = self.latencies

        def percentile(p):
            if not values:
                return None
            ordered = sorted(values)
            index = int((len(ordered) - 1) * p)
            return round(ordered[index], 3)

        return {
            **self.stats,
            "average_ms": (
                round(statistics.mean(values), 3)
                if values else None
            ),
            "minimum_ms": (
                round(min(values), 3)
                if values else None
            ),
            "maximum_ms": (
                round(max(values), 3)
                if values else None
            ),
            "p95_ms": percentile(0.95),
            "p99_ms": percentile(0.99)
        }
