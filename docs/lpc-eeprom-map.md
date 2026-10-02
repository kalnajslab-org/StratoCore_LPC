# LPC EEPROM Map

Teensy EEPROM bytes used by the LPC firmware. Claim new addresses here and in
the comment above `EEPROM_ADDR_RS41_RATE` in `src/StratoLPC.h`.

Only this repo's `src/` writes EEPROM — the vendored libraries (StratoCore,
StrateoleXML, RS41, StratoLinduino) do not use it. Two-byte values are stored
high byte first. Unwritten cells read `0xFF`.

| Addr | Size    | Contents                 | Owner / access | Notes |
|------|---------|--------------------------|----------------|-------|
| 0    | 1 byte  | Instrument type          | `LOPCLibrary::InstrumentType()` (`LOPCLibrary_revF.cpp`) | Valid values 1, 2 or 3. |
| 1    | 1 byte  | Serial number            | `LOPCLibrary` serial-number accessor | |
| 2-3  | 2 bytes | File counter             | `LOPCLibrary::FileNumber()` | Used as the data file extension; high byte written first with a 100 ms delay. |
| 4-5  | 2 bytes | RS41 sample period (s)   | `StratoLPC::ReadRS41SamplePeriodEEPROM()` / `WriteRS41SamplePeriodEEPROM()`, set by `SETRS41RATE` | Valid 1–300. Out-of-range/uninitialized falls back to `RS41_SAMPLE_PERIOD_SECS` (1 s). |
| 6+   | —       | Free                     | | |

Note: addresses 0–3 are written by LOPCLibrary, which is compiled into this
project (not vendored), so a new address must not overlap them.
