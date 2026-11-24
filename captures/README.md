# Captures

These folders are created by the scripts:

* `evidence/`: one `.pcapng` per key protocol exchange, from `python scripts/capture_evidence.py`. The `*_with_keys.pcapng` files embed the TLS secrets, so Wireshark decrypts DoT and DoH automatically. The raw key logs are in `evidence/keys/`.
* `screenshots/wireshark/`: annotated screenshots of the Wireshark GUI, one per trace. Each image names the trace file and the display filter used.
* `experiments/`: one capture per experiment run, from `python scripts/run_experiments.py`, with the key logs in `experiments/keys/`.
