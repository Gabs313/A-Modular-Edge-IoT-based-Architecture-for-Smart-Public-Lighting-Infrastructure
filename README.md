# A-Modular-Edge-IoT-based-Architecture-for-Smart-Public-Lighting-Infrastructure
Overview

A single-board computer (Raspberry Pi 5) acts as the master, polling two microcontroller-based slave nodes (ESP32-S3) over an RS-485 bus using a custom application-layer protocol with STX/ETX framing, JSON-encoded payloads, CRC-16 error detection, and a software-defined retry mechanism (up to three attempts per request). The two slave nodes carry intentionally distinct sensor suites, producing response payloads of 144 bytes (Node 1) and 100 bytes (Node 2), which lets the evaluation separate protocol behaviour from sensor-specific effects.

The experiments characterise the link along three axes:

Cable length — 1 m, 2 m, and 4 m (one-hour tests, four repetitions each).
Long-term stability — a five-hour continuous test on the 4 m cable (three repetitions, pooled).
CPU stress — synthetic master-side load stepped from 75 % to 95 % in 5 % increments, one hour per level, on the 4 m cable.

All experiments run at 9600 bps over unshielded twisted-pair cabling, with a 2-second hard-failure timeout.

Repository structure
<!-- TODO: edit this tree to match exactly what you upload. Delete any directory you are NOT releasing (e.g. firmware, if the industry partner has not cleared it). A README that lists files that are not present is worse than one that lists fewer. -->
.
├── data/                     # Raw measurement datasets (CSV)

├── analysis/

├── LICENSE

└── README.md

Each CSV contains one row per logical communication attempt, with the columns:

Column	              Meaning
timestamp	            UTC timestamp of the attempt
node_id	              Target slave node (1 or 2)
attempt_no	          Attempt index within the request
success	              True if a valid response was received
attempts	            Number of transmission attempts used (1–3)
rtt_ms	              Round-trip time in milliseconds
cpu_load_percent	    Master CPU load (CPU-sweep datasets only)
response_bytes_len	  Length of the received response payload
<!-- TODO: verify these column names against your actual CSV headers and edit to match. The table above must describe the files you upload. -->

A soft failure is an attempt that succeeded only after retransmission (success = True, attempts > 1); a hard failure is one that failed after all retries (success = False).

Hardware summary
Master: Raspberry Pi 5, USB-to-RS-485 converter.
Slaves: two ESP32-S3 modules, each with an RS-485 transceiver.
Node 1 sensors: BME680, SCD30, SPS30 (144-byte payload).
Node 2 sensors: SHT45, BMP390, SEN0460 (100-byte payload).
Bus: unshielded twisted-pair, 9600 bps.
License
<!-- TODO: choose and add a license. MIT or BSD-3-Clause are common for research code; CC-BY-4.0 is common for datasets. Confirm with all authors and the industry partner (Fisola / GreenGray) before publishing any firmware or protocol source. -->

See LICENSE.

Acknowledgment

This work was supported by FCT — Fundação para a Ciência e Tecnologia, I.P. (CeDRI: UID/05757/2025, UID/PRR/05757/2025; SusTEC: LA/P/0007/2020) and by COMPETE2030-FEDER-01482600 / LISBOA2030-FEDER-01482600 SMARTLIGHT.
