
import time
import queue
import mido
import statistics

from PySide6.QtCore import QThread, Signal


def make_packet(sequence):

    return mido.Message(
        "sysex",
        data=[
            0x7D,
            0x01,
            (sequence >> 21) & 0x7F,
            (sequence >> 14) & 0x7F,
            (sequence >> 7) & 0x7F,
            sequence & 0x7F
        ]
    )


def decode_packet(msg):

    if msg.type != "sysex":
        return None

    data = list(msg.data)

    if len(data) != 6:
        return None

    if data[0:2] != [0x7D, 0x01]:
        return None

    return (
        (data[2] << 21)
        | (data[3] << 14)
        | (data[4] << 7)
        | data[5]
    )


class BurstTest(QThread):

    progress = Signal(int, int)
    event = Signal(dict)
    completed = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        input_port,
        output_port,
        packet_count=500,
        interval_ms=5,
        timeout=3.0
    ):
        super().__init__()

        self.input_port = input_port
        self.output_port = output_port

        self.packet_count = packet_count
        self.interval_ms = interval_ms
        self.timeout = timeout

        self.running = True
        self.rx = queue.Queue()

    def stop(self):
        self.running = False

    def receive(self, msg):
        self.rx.put((msg.copy(), time.perf_counter()))

    def run(self):

        try:
            with mido.open_input(
                self.input_port,
                callback=self.receive
            ) as midi_in:

                with mido.open_output(
                    self.output_port
                ) as midi_out:

                    expected = {}
                    received_ids = set()
                    latencies = []

                    stats = {
                        "sent": 0,
                        "received": 0,
                        "lost": 0,
                        "duplicates": 0,
                        "unknown": 0,
                        "out_of_order": 0,
                        "late": 0
                    }

                    # Korábbi események ürítése a teszt előtt
                    while True:
                        try:
                            self.rx.get_nowait()
                        except queue.Empty:
                            break

                    print("Burst transmission started")

                    # Csomagok kiküldése
                    for seq in range(self.packet_count):

                        if not self.running:
                            break

                        sent_at = time.perf_counter()
                        expected[seq] = sent_at

                        midi_out.send(make_packet(seq))
                        stats["sent"] += 1

                        if self.interval_ms:
                            time.sleep(
                                self.interval_ms / 1000
                            )

                        if seq % 10 == 0:
                            self.progress.emit(
                                seq + 1,
                                self.packet_count
                            )

                    # Visszaérkezett csomagok vizsgálata
                    deadline = time.monotonic() + self.timeout

                    last_sequence = -1

                    while (
                        self.running
                        and time.monotonic() < deadline
                    ):

                        try:
                            msg, arrival = self.rx.get(
                                timeout=0.05
                            )
                        except queue.Empty:
                            continue

                        seq = decode_packet(msg)

                        if seq is None or seq not in expected:
                            stats["unknown"] += 1
                            continue

                        if seq in received_ids:
                            stats["duplicates"] += 1
                            continue

                        received_ids.add(seq)
                        stats["received"] += 1

                        latency = (
                            arrival - expected[seq]
                        ) * 1000

                        if latency > self.timeout * 1000:
                            stats["late"] += 1

                        latencies.append(latency)

                        if seq < last_sequence:
                            stats["out_of_order"] += 1

                        last_sequence = max(
                            last_sequence, seq
                        )

                        self.event.emit({
                            "sequence": seq,
                            "latency": latency,
                            "status": "RECEIVED"
                        })

                    # Csak a ténylegesen elküldött csomagok
                    # számítanak a hiány meghatározásánál.
                    stats["lost"] = (
                        stats["sent"] - stats["received"]
                    )

                    result = {
                        **stats,
                        "average_ms": (
                            statistics.mean(latencies)
                            if latencies else None
                        ),
                        "minimum_ms": (
                            min(latencies)
                            if latencies else None
                        ),
                        "maximum_ms": (
                            max(latencies)
                            if latencies else None
                        ),
                        "p95_ms": self.percentile(
                            latencies, 0.95
                        ),
                        "p99_ms": self.percentile(
                            latencies, 0.99
                        )
                    }

                    self.progress.emit(100, 100)
                    self.completed.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))

    @staticmethod
    def percentile(values, p):

        if not values:
            return None

        ordered = sorted(values)

        index = int(
            (len(ordered) - 1) * p
        )

        return round(ordered[index], 3)
