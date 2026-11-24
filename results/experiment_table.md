# Experiment table

Cells: mean ± standard deviation [min – max] over the run means (3 runs per condition). Condition = added RTT / packet loss per direction on the R1–R2 link.

| Metric | Label | 20 ms / 0 % | 100 ms / 0 % | 200 ms / 0 % | 20 ms / 2 % | 20 ms / 5 % |
|---|---|---|---|---|---|---|
| Iterative resolution time (ms) | www.example.lab | 65.5 ± 1.7 [64.2 – 67.4] | 303.9 ± 1.2 [303.0 – 305.3] | 605.3 ± 1.8 [603.5 – 607.1] | 198.8 ± 116.1 [64.7 – 265.9] | 400.7 ± 231.6 [264.7 – 668.1] |
| Iterative resolution time (ms) | mail.example.lab | 66.1 ± 2.0 [64.1 – 68.1] | 303.4 ± 0.6 [302.7 – 304.0] | 606.6 ± 1.0 [605.5 – 607.4] | 265.6 ± 198.8 [66.2 – 463.9] | 533.3 ± 231.4 [266.1 – 667.4] |
| Iterative resolution time (ms) | www.noglue.lab | 131.9 ± 3.4 [128.5 – 135.2] | 606.9 ± 2.2 [605.0 – 609.3] | 1211.9 ± 2.9 [1209.2 – 1214.9] | 330.8 ± 347.3 [127.3 – 731.9] | 934.4 ± 528.1 [538.5 – 1534.1] |
| Queries per lookup | www.example.lab | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] |
| Queries per lookup | mail.example.lab | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] |
| Queries per lookup | www.noglue.lab | 6.00 ± 0.00 [6.00 – 6.00] | 6.00 ± 0.00 [6.00 – 6.00] | 6.00 ± 0.00 [6.00 – 6.00] | 6.00 ± 0.00 [6.00 – 6.00] | 6.00 ± 0.00 [6.00 – 6.00] |
| Packets sent per lookup (incl. retries) | www.example.lab | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.13 ± 0.12 [3.00 – 3.20] | 3.33 ± 0.23 [3.20 – 3.60] |
| Packets sent per lookup (incl. retries) | mail.example.lab | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.00 ± 0.00 [3.00 – 3.00] | 3.20 ± 0.20 [3.00 – 3.40] | 3.47 ± 0.23 [3.20 – 3.60] |
| Packets sent per lookup (incl. retries) | www.noglue.lab | 6.00 ± 0.00 [6.00 – 6.00] | 6.00 ± 0.00 [6.00 – 6.00] | 6.00 ± 0.00 [6.00 – 6.00] | 6.20 ± 0.35 [6.00 – 6.60] | 6.80 ± 0.53 [6.40 – 7.40] |
| First-query latency, new connection (ms) | do53 | 22.8 ± 0.7 [22.3 – 23.6] | 101.8 ± 0.7 [101.2 – 102.5] | 202.0 ± 0.4 [201.6 – 202.4] | 89.7 ± 116.9 [22.0 – 224.7] | 89.1 ± 115.3 [21.5 – 222.3] |
| First-query latency, new connection (ms) | dot | 139.5 ± 5.0 [134.0 – 143.9] | 458.7 ± 8.9 [451.0 – 468.4] | 859.1 ± 1.6 [857.3 – 860.4] | 179.2 ± 23.1 [153.6 – 198.6] | 307.7 ± 144.5 [143.8 – 416.6] |
| First-query latency, new connection (ms) | doh | 115.6 ± 21.1 [102.9 – 139.9] | 337.7 ± 5.9 [333.3 – 344.4] | 699.6 ± 8.9 [691.1 – 708.7] | 224.2 ± 115.8 [135.5 – 355.2] | 203.8 ± 119.2 [119.6 – 340.2] |
| Repeat-query latency, reused connection (ms) | do53 | 22.6 ± 0.8 [21.8 – 23.4] | 101.2 ± 0.2 [101.0 – 101.3] | 201.8 ± 0.3 [201.5 – 202.1] | 55.6 ± 58.3 [21.8 – 122.9] | 121.9 ± 100.2 [21.8 – 222.3] |
| Repeat-query latency, reused connection (ms) | dot | 22.4 ± 0.8 [21.5 – 23.1] | 101.4 ± 0.5 [101.1 – 102.0] | 202.1 ± 0.5 [201.7 – 202.6] | 21.9 ± 1.1 [21.2 – 23.2] | 29.5 ± 13.5 [21.4 – 45.0] |
| Repeat-query latency, reused connection (ms) | doh | 23.8 ± 2.4 [21.9 – 26.5] | 103.3 ± 0.5 [102.8 – 103.8] | 206.1 ± 0.9 [205.4 – 207.1] | 44.9 ± 28.1 [26.9 – 77.3] | 52.2 ± 27.4 [32.8 – 83.5] |
| Do53 via Unbound, cold cache (ms) | unbound (cache flushed) | 28.3 ± 5.0 [24.0 – 33.8] | 104.3 ± 0.9 [103.4 – 105.2] | 207.6 ± 5.4 [204.0 – 213.9] | 35.7 ± 6.2 [31.0 – 42.7] | 34.4 ± 11.6 [23.3 – 46.4] |
| Round trips before the DNS query is sent | do53 | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] |
| Round trips before the DNS query is sent | dot | 3.32 ± 0.26 [3.09 – 3.59] | 2.21 ± 0.22 [2.07 – 2.46] | 2.11 ± 0.06 [2.06 – 2.17] | 3.08 ± 0.56 [2.44 – 3.41] | 2.12 ± 0.93 [1.06 – 2.81] |
| Round trips before the DNS query is sent | doh | 3.44 ± 0.12 [3.33 – 3.57] | 2.18 ± 0.08 [2.11 – 2.26] | 2.34 ± 0.13 [2.19 – 2.44] | 4.48 ± 2.58 [2.66 – 7.44] | 2.67 ± 0.19 [2.45 – 2.81] |
| Packets up to the first DNS response | do53 | 2.0 ± 0.0 [2.0 – 2.0] | 2.0 ± 0.0 [2.0 – 2.0] | 2.0 ± 0.0 [2.0 – 2.0] | 2.0 ± 0.0 [2.0 – 2.0] | 2.0 ± 0.0 [2.0 – 2.0] |
| Packets up to the first DNS response | dot | 13.0 ± 0.0 [13.0 – 13.0] | 13.0 ± 0.0 [13.0 – 13.0] | 13.0 ± 0.0 [13.0 – 13.0] | 13.0 ± 0.0 [13.0 – 13.0] | 14.0 ± 1.7 [13.0 – 16.0] |
| Packets up to the first DNS response | doh | 21.0 ± 0.0 [21.0 – 21.0] | 21.0 ± 0.0 [21.0 – 21.0] | 22.7 ± 1.5 [21.0 – 24.0] | 21.3 ± 1.5 [20.0 – 23.0] | 21.0 ± 0.0 [21.0 – 21.0] |
| Bytes on the wire, 1-query session (B) | do53 | 166 ± 0 [166 – 166] | 166 ± 0 [166 – 166] | 166 ± 0 [166 – 166] | 166 ± 0 [166 – 166] | 166 ± 0 [166 – 166] |
| Bytes on the wire, 1-query session (B) | dot | 3047 ± 1 [3046 – 3047] | 3046 ± 1 [3046 – 3047] | 3046 ± 1 [3045 – 3047] | 3046 ± 1 [3045 – 3047] | 3118 ± 123 [3046 – 3260] |
| Bytes on the wire, 1-query session (B) | doh | 4019 ± 1 [4018 – 4020] | 4019 ± 1 [4018 – 4020] | 4107 ± 76 [4020 – 4151] | 4041 ± 101 [3953 – 4151] | 4183 ± 170 [4018 – 4357] |
| Bytes per repeat query on open connection (B) | do53 | 166 ± 0 [166 – 166] | 166 ± 0 [166 – 166] | 166 ± 0 [166 – 166] | 166 ± 0 [166 – 166] | 175 ± 11 [166 – 187] |
| Bytes per repeat query on open connection (B) | dot | 264 ± 8 [255 – 269] | 269 ± 0 [268 – 269] | 269 ± 0 [268 – 269] | 276 ± 12 [262 – 284] | 301 ± 66 [254 – 376] |
| Bytes per repeat query on open connection (B) | doh | 732 ± 4 [728 – 735] | 726 ± 4 [721 – 728] | 721 ± 7 [715 – 728] | 728 ± 17 [716 – 748] | 789 ± 105 [703 – 906] |
| Bytes on the wire per iterative lookup (B) | www.example.lab | 578 ± 0 [578 – 578] | 578 ± 0 [578 – 578] | 578 ± 0 [578 – 578] | 578 ± 0 [578 – 578] | 578 ± 0 [578 – 578] |
| Bytes on the wire per iterative lookup (B) | mail.example.lab | 584 ± 0 [584 – 584] | 584 ± 0 [584 – 584] | 584 ± 0 [584 – 584] | 584 ± 0 [584 – 584] | 609 ± 44 [584 – 660] |
| Bytes on the wire per iterative lookup (B) | www.noglue.lab | 1132 ± 0 [1132 – 1132] | 1132 ± 0 [1132 – 1132] | 1132 ± 0 [1132 – 1132] | 1132 ± 0 [1132 – 1132] | 1157 ± 43 [1132 – 1206] |
| Iterative time from packet timestamps (ms) | www.example.lab | 65.0 ± 2.2 [62.4 – 66.3] | 303.3 ± 1.9 [302.1 – 305.5] | 607.9 ± 3.0 [605.0 – 610.9] | 67.0 ± 5.1 [62.6 – 72.5] | 66.2 ± 1.4 [64.8 – 67.5] |
| Iterative time from packet timestamps (ms) | mail.example.lab | 63.6 ± 1.7 [62.0 – 65.3] | 312.6 ± 17.3 [302.4 – 332.6] | 604.6 ± 1.4 [603.6 – 606.1] | 115.2 ± 89.2 [63.2 – 218.1] | 400.8 ± 580.4 [63.2 – 1071.0] |
| Iterative time from packet timestamps (ms) | www.noglue.lab | 131.2 ± 4.8 [126.0 – 135.4] | 605.8 ± 1.0 [604.7 – 606.8] | 1212.1 ± 2.5 [1209.2 – 1214.0] | 129.8 ± 3.0 [126.6 – 132.7] | 463.7 ± 579.6 [127.7 – 1132.9] |
| Resolver timer minus capture timer (ms) | www.example.lab | 0.90 ± 0.39 [0.46 – 1.24] | 0.45 ± 0.11 [0.36 – 0.57] | 0.73 ± 0.23 [0.50 – 0.97] | 0.48 ± 0.09 [0.41 – 0.58] | 1.06 ± 0.22 [0.85 – 1.29] |
| Resolver timer minus capture timer (ms) | mail.example.lab | 0.69 ± 0.29 [0.48 – 1.02] | 0.42 ± 0.07 [0.34 – 0.46] | 0.71 ± 0.07 [0.64 – 0.78] | 0.67 ± 0.22 [0.45 – 0.89] | 0.98 ± 0.40 [0.56 – 1.36] |
| Resolver timer minus capture timer (ms) | www.noglue.lab | 0.94 ± 0.49 [0.48 – 1.45] | 0.38 ± 0.09 [0.29 – 0.45] | 1.29 ± 0.31 [0.96 – 1.58] | 0.83 ± 0.52 [0.42 – 1.41] | 1.08 ± 0.78 [0.57 – 1.98] |
| Failed transport queries per run | do53 | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] |
| Failed transport queries per run | dot | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] |
| Failed transport queries per run | doh | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] |
| Failed iterative lookups per run | www.example.lab | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] |
| Failed iterative lookups per run | mail.example.lab | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] |
| Failed iterative lookups per run | www.noglue.lab | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] | 0.00 ± 0.00 [0.00 – 0.00] |

### Per-step resolution time (ms), delay sweep

| Lookup step | 20 ms / 0 % | 100 ms / 0 % | 200 ms / 0 % |
|---|---|---|---|
| www.example.lab — step 1: www.example.lab. @ zone . | 21.5 ± 0.4 | 101.0 ± 0.2 | 201.6 ± 0.5 |
| www.example.lab — step 2: www.example.lab. @ zone lab. | 21.8 ± 0.5 | 101.1 ± 0.3 | 201.6 ± 0.5 |
| www.example.lab — step 3: www.example.lab. @ zone example.lab. | 21.6 ± 0.6 | 101.4 ± 0.6 | 201.6 ± 0.6 |
| mail.example.lab — step 1: mail.example.lab. @ zone . | 21.8 ± 0.5 | 101.0 ± 0.3 | 201.7 ± 0.6 |
| mail.example.lab — step 2: mail.example.lab. @ zone lab. | 21.9 ± 0.7 | 100.9 ± 0.2 | 202.3 ± 0.5 |
| mail.example.lab — step 3: mail.example.lab. @ zone example.lab. | 21.7 ± 0.6 | 101.1 ± 0.2 | 202.0 ± 0.7 |
| www.noglue.lab — step 1: www.noglue.lab. @ zone . | 21.7 ± 0.3 | 100.9 ± 0.1 | 201.6 ± 0.1 |
| www.noglue.lab — step 2: www.noglue.lab. @ zone lab. | 21.7 ± 0.4 | 101.4 ± 1.1 | 202.1 ± 1.0 |
| www.noglue.lab — step 3: ns.example.lab. @ zone . | 21.8 ± 0.4 | 101.2 ± 0.7 | 201.3 ± 0.2 |
| www.noglue.lab — step 4: ns.example.lab. @ zone lab. | 21.8 ± 0.6 | 101.0 ± 0.1 | 201.5 ± 0.4 |
| www.noglue.lab — step 5: ns.example.lab. @ zone example.lab. | 21.6 ± 0.3 | 101.0 ± 0.3 | 201.8 ± 0.5 |
| www.noglue.lab — step 6: www.noglue.lab. @ zone noglue.lab. | 22.2 ± 1.2 | 100.8 ± 0.1 | 201.6 ± 0.6 |
