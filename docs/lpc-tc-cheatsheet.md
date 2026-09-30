# LPC Telecommand Cheatsheet

The telecommands `StratoLPC::TCHandler()` actually acts on — IDs 100–120 (the
LPC block) plus the generic commands that apply to any instrument. Commands
that exist in the shared enum but aren't wired up in `TCHandler()`
(`SETMODE`, `GETFILE`, `SETHGBINS`, `SETLGBINS`, `SETHKPERIOD`, `EXITERROR`)
are left out here — sending one still gets acked (`TCHandler()` returns
`true` on every branch, including the fallthrough default), it just does
nothing.

Source: `StrateoleXML/Telecommand.h` and `StratoLPC.cpp`. This is a snapshot,
not a live read of the firmware — re-check it after either file changes.

## LPC settings

| ID  | Name           | Params                                              | Notes |
|-----|----------------|------------------------------------------------------|-------|
| 101 | `SETSAMPLE`    | `samples`: uint16                                     | → `Set_numberSamples`. PHA frames per measurement cycle. Default `60`. |
| 102 | `SETWARMUPTIME`| `warmUpTime`: uint16 (s)                              | → `Set_warmUpTime`. Default `10s`. |
| 103 | `SETCYCLETIME` | `setCycleTime`: uint8 (min)                           | → `Set_cycleTime`. Also the interval used to schedule the next `START_WARMUP`. Default `15 min`. |
| 107 | `SETLASERTEMP` | `setLaserTemp`: uint8 (°C)                            | → `Set_LaserTemp`. Default `-30°C`. |
| 109 | `SETFLUSH`     | `lpc_flush`: uint8 (s)                                | → `Set_FlushingTime`. Default `10s`. |
| 110 | `SETSAMPLEAVG` | `samplesToAverage`: uint16                            | → `Set_samplesToAverage`. PHA frames averaged per HK sample. Default `1`. |
| 116 | `SETPHA`       | `phaHiGainThreshold`, `phaHiGainOffset`, `phaLoGainOffset`: uint16 | Stores all three and sets `Set_triggerPHAconfig`; applied to the PHA by `phaConfig()` at the next `FL_WARMUP`, not immediately. |
| 117 | `REGENRS41`    | —                                                      | Sets `Set_rs41regen`; the actual `recondition()` call happens on the next `RS41_SAMPLE` tick, not synchronously. |
| 118 | `SETFLOW`      | `flowSetpoint`: float                                 | Sets `BEMF1_SP` **and** `BEMF2_SP` — one value drives both pumps. Default `7.8V`. |
| 119 | `SETPUMPTEMP`  | `pumpMinTemp`: float (°C)                             | → `PumpMinTemp`. Below this, `FL_IDLE` shuts back down instead of starting warm-up. Default `-20°C`. |
| 120 | `SETRS41RATE`  | `rs41SamplePeriod`: uint16 (s)                        | Range-checked 1–300s (out of range → warning, ignored); persisted to EEPROM addr 4. Report/local-file cadence is a fixed 300 samples, so it scales with this value. |

IDs 111–115 are reserved in `TCMessage.py` and not defined in this firmware's
`Telecommand_t` — do not reuse.

## Generic commands (any instrument)

| ID  | Name          | Params | Notes |
|-----|---------------|--------|-------|
| 200 | `RESET_INST`  | —      | Acks, then writes the ARM AIRCR reset key — the Teensy reboots immediately. Intercepted by StratoCore before reaching `TCHandler`. |
| 202 | `GETTMBUFFER` | —      | Sends the TM buffer. Intercepted by StratoCore before `TCHandler`. |
| 203 | `SENDSTATE`   | —      | Logs current mode/substate via `ZephyrLogFine`. Intercepted by StratoCore before `TCHandler`. |

## Current defaults

| Setting | Default |
|---|---|
| `numberSamples` | `60` |
| `samplesToAverage` | `1` |
| `cycleTime` | `15 min` |
| `warmUpTime` | `10 s` |
| `flushingTime` | `10 s` |
| `laserTemp` | `-30°C` |
| `pumpMinTemp` | `-20°C` |
| BEMF setpoint (both pumps) | `7.8 V` |
| RS41 sample period | `1 s` (EEPROM-backed, range 1–300s) |
