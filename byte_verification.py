
class ByteVerifier:

    @staticmethod
    def compare(expected, received):

        expected = bytes(expected)
        received = bytes(received)

        differences = []

        max_length = max(
            len(expected),
            len(received)
        )

        for index in range(max_length):

            tx = (
                expected[index]
                if index < len(expected)
                else None
            )

            rx = (
                received[index]
                if index < len(received)
                else None
            )

            if tx != rx:
                differences.append({
                    "position": index + 1,
                    "expected": tx,
                    "received": rx,
                    "expected_hex": (
                        f"{tx:02X}" if tx is not None else "--"
                    ),
                    "received_hex": (
                        f"{rx:02X}" if rx is not None else "--"
                    )
                })

        return {
            "passed": len(differences) == 0,
            "expected_length": len(expected),
            "received_length": len(received),
            "length_match": len(expected) == len(received),
            "expected_hex": expected.hex(" ").upper(),
            "received_hex": received.hex(" ").upper(),
            "byte_errors": len(differences),
            "differences": differences
        }
