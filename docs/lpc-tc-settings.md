# LPC Telecommand Settings: Power-up Values, Variables, Persistence

For each LPC telecommand: the member variable it sets in `StratoLPC`
(`src/StratoLPC.h`), the value the variable has at power-up, and whether it is
saved in EEPROM. Only `SETRS41RATE` is persisted; every other setting reverts
to the compiled-in default on reboot. See `lpc-tc-cheatsheet.md` for the
parameter formats and `lpc-eeprom-map.md` for the EEPROM layout.

| ID  | TC              | Variable(s) set                                              | Power-up value | In EEPROM? |
|-----|-----------------|--------------------------------------------------------------|----------------|------------|
| 101 | `SETSAMPLE`     | `Set_numberSamples`                                          | `75`           | No |
| 102 | `SETWARMUPTIME` | `Set_warmUpTime` (s)                                         | `10`           | No |
| 103 | `SETCYCLETIME`  | `Set_cycleTime` (min)                                        | `30`           | No |
| 107 | `SETLASERTEMP`  | `Set_LaserTemp` (°C)                                         | `-30`          | No |
| 109 | `SETFLUSH`      | `Set_FlushingTime` (s)                                       | `10`           | No |
| 110 | `SETSAMPLEAVG`  | `Set_samplesToAverage`                                       | `1`            | No |
| 116 | `SETPHA`        | `Set_phaHiGainThreshold`, `Set_phaHiGainOffset`, `Set_phaLoGainOffset`; also sets `Set_triggerPHAconfig` | `0` (no initializer; zero-initialized because `strato` is a global); `Set_triggerPHAconfig = false` | No |
| 117 | `REGENRS41`     | `Set_rs41regen` (one-shot, cleared after the regen runs)     | `false`        | No |
| 118 | `SETFLOW`       | `BEMF1_SP` and `BEMF2_SP` (V)                                | `7.8`          | No |
| 119 | `SETPUMPTEMP`   | `PumpMinTemp` (°C)                                           | `-20.0`        | No |
| 120 | `SETRS41RATE`   | `Set_rs41SamplePeriod` (s)                                   | EEPROM value if 1–300, else `RS41_SAMPLE_PERIOD_SECS` (`1`) | **Yes**, addr 4–5 |
| 121 | `MANUALMEASURE` | `Manual_warmup_pending` (then `Manual_measurement`, `Manual_missed`, `Manual_missed_time`) | `false` / `false` / `false` / `0` | No |

`SETHGBINS` (105) and `SETLGBINS` (106) are accepted but not implemented, so
`Set_HGBinBoundaries` and `Set_LGBinBoundaries` (compiled-in per instrument)
are unaffected.

Notes:
- `Set_rs41SamplePeriod` is loaded from EEPROM in `InstrumentSetup()`, so a
  value set by `SETRS41RATE` survives a reboot; the others do not.
- `SETPHA` values are applied to the PHA by `phaConfig()` at the next
  `FL_WARMUP`. Values are range-checked there, not in the TC handler.
- The `SET*` handlers other than `SETRS41RATE` have no range checking in
  `TCHandler()` (`// todo: checking`), apart from any done when parsing the TC.
