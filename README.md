# Xenoblade Chronicles: Definitive Edition Save Editor

A Python tool for modifying Xenoblade Chronicles: Definitive Edition save files. This editor provides an `argparse`-based command-line interface for changing character levels, XP, AP, arts levels and unlock thresholds, and in-game money (Gold), without needing to use the more complex C# library.

## Features

- View character stats (Level, XP, AP) and current Gold
- Modify a character's level, XP, or AP
- Set all characters to the same level at once
- View arts levels and max unlock levels
- Modify arts levels and max unlock thresholds
- Set all arts to a given level or max unlock at once
- Set in-game money (Gold)
- Validates save files before editing (size + sanity check)
- Supports both the modern subcommand syntax and the legacy positional syntax

## Requirements

- Python 3.6 or higher

## Installation

1. Download the `xcde_editor.py` script
2. Place it in a directory with your save files or where you have access to them

## Save File Location

- On Nintendo Switch: Save files are stored on the console (requires custom firmware to access)
- On Yuzu or Ryujinx emulators: Save files are typically located in the emulator's save directory
  - Save file format: `bfsgame0xx.sav` (where xx is the save slot number)

## Usage

The editor uses a subcommand-based CLI. Run it without a command to view stats:

```bash
python xcde_editor.py path/to/your/savefile.sav
```

Each modification command also accepts two global options:

| Option | Description |
|---|---|
| `--dry-run` | Preview the change without writing anything to disk |
| `-o, --output PATH` | Custom output path (default: `<save_file>.modified`) |

### Modify a Character's XP

```bash
python xcde_editor.py <save_file> set-xp <character_id> <new_xp>
```

Example:
```bash
python xcde_editor.py bfsgame01.sav set-xp 1 500000
```
This sets Shulk's (ID 1) XP to 500,000.

### Modify a Character's Level

```bash
python xcde_editor.py <save_file> set-level <character_id> <new_level>
```

Example:
```bash
python xcde_editor.py bfsgame01.sav set-level 2 99
```
This sets Reyn's (ID 2) level to 99.

### Modify a Character's AP

```bash
python xcde_editor.py <save_file> set-ap <character_id> <new_ap>
```

Example:
```bash
python xcde_editor.py bfsgame01.sav set-ap 1 99999
```
This sets Shulk's AP to 99,999.

### Set All Characters to the Same Level

```bash
python xcde_editor.py <save_file> set-all-level <new_level>
```

Example:
```bash
python xcde_editor.py bfsgame01.sav set-all-level 99
```
This sets all characters to level 99.

### Set All Arts to a Specific Level

```bash
python xcde_editor.py <save_file> set-all-art-level <new_level>
```

Example:
```bash
python xcde_editor.py bfsgame01.sav set-all-art-level 12
```
This sets all arts to level 12 (max level).

### Set Max Unlock Level for All Arts

```bash
python xcde_editor.py <save_file> set-all-art-max <new_max_level>
```

Max level values:
- 0: IV_BEGINNER (up to level 4)
- 1: VII_INTERMEDIATE (up to level 7)
- 2: X_EXPERT (up to level 10)
- 3: XII_MASTER (up to level 12)

Example:
```bash
python xcde_editor.py bfsgame01.sav set-all-art-max 3
```
This allows all arts to be upgraded to level 12 (XII_MASTER).

### Set Money (Gold)

```bash
python xcde_editor.py <save_file> set-money <new_money>
```

Example:
```bash
python xcde_editor.py bfsgame01.sav set-money 9999999
```

## Command Shortcuts

Each subcommand has a short alias:

| Command | Alias | Description |
|---|---|---|
| `set-level` | `sl` | Set a character's level |
| `set-all-level` | `sal` | Set all characters to a level |
| `set-xp` | `sxp` | Set a character's XP |
| `set-ap` | `sap` | Set a character's AP |
| `set-all-art-level` | `saal` | Set level for all arts |
| `set-all-art-max` | `saam` | Set max unlock for all arts |
| `set-money` | `sm` | Set money (Gold) |

Example using an alias:
```bash
python xcde_editor.py bfsgame01.sav sl 2 99
```

## Legacy Syntax (Still Supported)

Older positional command forms continue to work and are mapped to the new subcommands internally:

| Legacy | Equivalent |
|---|---|
| `<file> <char_id> <xp>` | `set-xp` |
| `<file> level <char_id> <lvl>` | `set-level` |
| `<file> ap <char_id> <ap>` | `set-ap` |
| `<file> alllevel <lvl>` | `set-all-level` |
| `<file> allartlevel <lvl>` | `set-all-art-level` |
| `<file> allartmax <max>` | `set-all-art-max` |
| `<file> money <amount>` | `set-money` |

Example:
```bash
python xcde_editor.py bfsgame01.sav level 2 99   # same as: set-level 2 99
```

## Character IDs

| ID | Character |
|---|---|
| 1 | SHULK |
| 2 | REYN |
| 3 | FIORA |
| 4 | DUNBAN |
| 5 | SHARLA |
| 6 | RIKI |
| 7 | MELIA |
| 8 | FIORA_2 |
| 9 | DICKSON |
| 10 | MUMKHAR |
| 11 | ALVIS |
| 12 | DUNBAN_2 |
| 13 | DUNBAN_3 |
| 14 | KINO |
| 15 | NENE |

## Safety Features

- Save files are validated before any editing (file size and an in-place sanity check of the first character's level)
- A backup of the original save file is created automatically before the first modification
- Modified saves are written to a new file with a `.modified` extension (or a custom path via `-o`/`--output`) to avoid overwriting your original
- Use `--dry-run` to preview a change without writing anything to disk
- All modifications include validation to help prevent corruption

## Advanced Usage

If you need more advanced save editing functionality, consider checking out the original C# library this editor is based on at [damysteryman/XCDESave](https://github.com/damysteryman/XCDESave).

## Credits

This editor is based on the save file structure reverse-engineered by damysteryman's XCDESave C# library. The Python implementation provides a simplified interface for the most common editing needs.

## License

This tool is provided under the GNU General Public License v3, the same as the original C# library it's based on.

## Warning

- Modifying save files could potentially corrupt them or lead to issues in the game. Always use the backups if something goes wrong.
- This editor doesn't modify checksums (if any exist in the save file), which might cause issues in some game versions.
