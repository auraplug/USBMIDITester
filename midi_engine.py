
import mido
import queue
import time

from byte_verification import ByteVerifier


class MidiEngine:

    def __init__(self):
        self.input = None
        self.output = None
        self.rx = queue.Queue()

        self.late_messages = 0
        self.unexpected_messages = 0
        self.duplicate_messages = 0
        self.last_byte_error = None

    @staticmethod
    def input_ports():
        return mido.get_input_names()

    @staticmethod
    def output_ports():
        return mido.get_output_names()

    def open(self, input_name, output_name):
        self.close()

        self.rx = queue.Queue()

        self.input = mido.open_input(
            input_name,
            callback=self._receive
        )

        self.output = mido.open_output(output_name)

    def _receive(self, msg):
        self.rx.put((msg.copy(), time.perf_counter()))

    def send_and_wait(self, msg, timeout=0.5, grace=0.03):

        if not self.input or not self.output:
            raise RuntimeError("MIDI port nincs megnyitva")

        expected = bytes(msg.bytes())
        start = time.perf_counter()
        deadline = start + timeout

        self.output.send(msg)

        mismatch = 0
        duplicates = 0
        latency = None
        matched = False
        last_comparison = None

        while time.perf_counter() < deadline:

            try:
                received, arrival = self.rx.get(
                    timeout=max(
                        0.001,
                        deadline - time.perf_counter()
                    )
                )
            except queue.Empty:
                break

            actual = bytes(received.bytes())

            comparison = ByteVerifier.compare(
                expected,
                actual
            )

            if comparison["passed"]:

                if not matched:
                    latency = (arrival - start) * 1000
                    matched = True

                    deadline = min(
                        deadline,
                        time.perf_counter() + grace
                    )

                else:
                    duplicates += 1
                    self.duplicate_messages += 1

            else:
                mismatch += 1
                self.unexpected_messages += 1
                last_comparison = comparison

        verification = (
            ByteVerifier.compare(expected, expected)
            if matched else last_comparison
        )

        return {
            "status": (
                "PASS" if matched
                else "BYTE_MISMATCH" if last_comparison
                else "TIMEOUT"
            ),
            "latency": latency,
            "duplicates": duplicates,
            "mismatch": mismatch,
            "byte_verification": verification
        }

    def close(self):

        if self.input:
            self.input.close()
            self.input = None

        if self.output:
            self.output.close()
            self.output = None
