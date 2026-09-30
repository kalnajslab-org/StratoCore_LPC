# LPC Telecommand Cheatsheet

Every telecommand `StratoLPC::TCHandler()` can receive — IDs 100–120 (the LPC
block) plus the generic commands that apply to any instrument.

Source: `StrateoleXML/Telecommand.h` and `StratoLPC.cpp`. This is a snapshot,
not a live read of the firmware — re-check it after either file changes.

## Ack ≠ implemented

`TCHandler()` always returns `true` (ack) no matter which branch it takes —
including the `default` case. Sending `SETHGBINS`, `SETMODE`, or any command
marked **not wired** below gets acked exactly like a real one; only the
console log (or its absence) tells you it did nothing. Don't take an ack as
confirmation for anything marked **not wired** or **unimplemented** below.

**Status legend**

- ✅ **implemented**
- ⚠️ **not wired** — falls to `"Unknown TC received"`
- ⛔ **unimplemented** — the case exists, but does nothing useful yet

## LPC settings (100–120)

| ID  | Name           | Params                                              | Status            | Notes |
|-----|----------------|------------------------------------------------------|-------------------|-------|
| 100 | `SETMODE`      | `mode`: enum                                          | ⚠️ not wired       | Mode switching is handled by the StratoCore framework, not this TC — expect it to fall to `"Unknown TC received"` here. |
| 101 | `SETSAMPLE`    | `samples`: uint16                                     | ✅ implemented     | → `Set_numberSamples`. PHA frames per measurement cycle. Default `60`. |
| 102 | `SETWARMUPTIME`| `warmUpTime`: uint16 (s)                              | ✅ implemented     | → `Set_warmUpTime`. Default `10s`. |
| 103 | `SETCYCLETIME` | `setCycleTime`: uint8 (min)                           | ✅ implemented     | → `Set_cycleTime`. Also the interval used to schedule the next `START_WARMUP`. Default `15 min`. |
| 104 | `GETFILE`      | `getFrameFile`: uint32                                | ⚠️ not wired       | Requested frame number never reaches a handler in `StratoLPC.cpp`. |
| 105 | `SETHGBINS`    | `setHGBins`: uint8, `newHGBins[24]`: uint8             | ⛔ unimplemented   | Logs `"HG bins unimplemented"` and stops. Reader delivers 24 values; the class holds 16 — the shape was never reconciled. |
| 106 | `SETLGBINS`    | `setLGBins`: uint8, `newLGBins[24]`: uint8             | ⛔ unimplemented   | Same as `SETHGBINS`, LG channel. |
| 107 | `SETLASERTEMP` | `setLaserTemp`: uint8 (°C)                            | ✅ implemented     | → `Set_LaserTemp`. Default `-30°C`. |
| 108 | `SETHKPERIOD`  | `hkPeriod`: uint8 (min)                               | ⚠️ not wired       | Defined in the shared enum, never reaches a case here. |
| 109 | `SETFLUSH`     | `lpc_flush`: uint8 (s)                                | ✅ implemented     | → `Set_FlushingTime`. Default `10s`. |
| 110 | `SETSAMPLEAVG` | `samplesToAverage`: uint16                            | ✅ implemented     | → `Set_samplesToAverage`. PHA frames averaged per HK sample. Default `1`. |
| 111–115 | —          | —                                                      | —                 | Reserved in `TCMessage.py`; not defined in this firmware's `Telecommand_t` — do not reuse. |
| 116 | `SETPHA`       | `phaHiGainThreshold`, `phaHiGainOffset`, `phaLoGainOffset`: uint16 | ✅ implemented | Stores all three and sets `Set_triggerPHAconfig`; applied to the PHA by `phaConfig()` at the next `FL_WARMUP`, not immediately. |
| 117 | `REGENRS41`    | —                                                      | ✅ implemented     | Sets `Set_rs41regen`; the actual `recondition()` call happens on the next `RS41_SAMPLE` tick, not synchronously. |
| 118 | `SETFLOW`      | `flowSetpoint`: float                                 | ✅ implemented     | Sets `BEMF1_SP` **and** `BEMF2_SP` — one value drives both pumps. Default `7.8V`. |
| 119 | `SETPUMPTEMP`  | `pumpMinTemp`: float (°C)                             | ✅ implemented     | → `PumpMinTemp`. Below this, `FL_IDLE` shuts back down instead of starting warm-up. Default `-20°C`. |
| 120 | `SETRS41RATE`  | `rs41SamplePeriod`: uint16 (s)                        | ✅ implemented     | Range-checked 1–300s (out of range → warning, ignored); persisted to EEPROM addr 4. Report/local-file cadence is a fixed 300 samples, so it scales with this value. |

## Generic commands (any instrument)

| ID  | Name          | Params | Status         | Notes |
|-----|---------------|--------|----------------|-------|
| 200 | `RESET_INST`  | —      | ✅ implemented | Acks, then writes the ARM AIRCR reset key — the Teensy reboots immediately. Intercepted by StratoCore before reaching `TCHandler`. |
| 201 | `EXITERROR`   | —      | ⚠️ not wired    | Defined in the shared enum but neither intercepted generically nor handled in StratoLPC — falls to `"Unknown TC received"`. Leaving `FL_ERROR` currently needs a mode-switch command instead. |
| 202 | `GETTMBUFFER` | —      | ✅ implemented | Sends the TM buffer. Intercepted by StratoCore before `TCHandler`. |
| 203 | `SENDSTATE`   | —      | ✅ implemented | Logs current mode/substate via `ZephyrLogFine`. Intercepted by StratoCore before `TCHandler`. |

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
