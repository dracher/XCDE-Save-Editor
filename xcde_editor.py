#!/usr/bin/env python3
"""
Xenoblade Chronicles: Definitive Edition Save Editor

A Python tool for modifying XCDE save files. Supports editing character levels,
XP, AP, arts levels/max unlock, and in-game money (Gold).

Based on the save file structure reverse-engineered by damysteryman's XCDESave C# library.
"""

import argparse
import os
import struct
import sys
from enum import IntEnum

# ── Constants ──────────────────────────────────────────────────────────────────

# Minimum valid save file size (bytes): must cover the arts data block
MIN_SAVE_FILE_SIZE = 0x153860  # ARTS_LEVELS_OFFSET + TOTAL_ARTS * ARTS_LEVEL_SIZE
MAX_MONEY_VALUE = 0xFFFFFFFF
MAX_LEVEL = 99
MAX_ART_LEVEL = 12
MAX_ART_UNLOCK = 3
TOTAL_MAIN_CHARACTERS = 15  # IDs 1-15


# ── Enums ───────────────────────────────────────────────────────────────────────

class Character(IntEnum):
    """Character IDs for Xenoblade Chronicles: Definitive Edition"""

    NONE = 0
    SHULK = 1
    REYN = 2
    FIORA = 3
    DUNBAN = 4
    SHARLA = 5
    RIKI = 6
    MELIA = 7
    FIORA_2 = 8
    DICKSON = 9
    MUMKHAR = 10
    ALVIS = 11
    DUNBAN_2 = 12
    DUNBAN_3 = 13
    KINO = 14
    NENE = 15
    WUNWUN = 16
    TUTU = 17
    DRYDRY = 18
    FOFORA = 19
    FAIFA = 20
    HEKASA = 21
    SETSET = 22
    TEITEI = 23
    NONONA = 24
    DEKADEKA = 25
    EVELEN = 26
    TENTOO = 27


class ArtsLevelUnlocked(IntEnum):
    """Max level that arts can be unlocked to"""

    IV_BEGINNER = 0  # Up to level 4
    VII_INTERMEDIATE = 1  # Up to level 7
    X_EXPERT = 2  # Up to level 10
    XII_MASTER = 3  # Up to level 12


# Character positions in PartyMembers array (IDs 1-15)
CHARACTER_POSITIONS = {
    Character.SHULK: 0,
    Character.REYN: 1,
    Character.FIORA: 2,
    Character.DUNBAN: 3,
    Character.SHARLA: 4,
    Character.RIKI: 5,
    Character.MELIA: 6,
    Character.FIORA_2: 7,
    Character.DICKSON: 8,
    Character.MUMKHAR: 9,
    Character.ALVIS: 10,
    Character.DUNBAN_2: 11,
    Character.DUNBAN_3: 12,
    Character.KINO: 13,
    Character.NENE: 14,
}

# Legacy command → new subcommand name mapping
LEGACY_COMMAND_MAP = {
    "level": "set-level",
    "ap": "set-ap",
    "alllevel": "set-all-level",
    "allartlevel": "set-all-art-level",
    "allartmax": "set-all-art-max",
    "money": "set-money",
}


# ── Save Editor ─────────────────────────────────────────────────────────────────

class XCDESaveEditor:
    # Important offsets in the save file
    PARTY_MEMBERS_OFFSET = 0x152368
    PARTY_MEMBER_SIZE = 0x138
    EXP_OFFSET_IN_MEMBER = 0x04
    LEVEL_OFFSET_IN_MEMBER = 0x00
    AP_OFFSET_IN_MEMBER = 0x08

    # Arts levels offset and size
    ARTS_LEVELS_OFFSET = 0x1536E8
    ARTS_LEVEL_SIZE = 2
    TOTAL_ARTS = 188

    # Money (Gold) offset
    MONEY_OFFSET = 0x151B40

    def __init__(self, save_path):
        """Initialize the editor with the path to the save file"""
        self.save_path = save_path
        self.backup_path = save_path + ".backup"
        self._backup_created = False

        # Validate and read the save file
        self._validate_save_file(save_path)
        with open(save_path, "rb") as f:
            self.save_data = bytearray(f.read())

    def _validate_save_file(self, save_path):
        """Validate that the file looks like a valid XCDE save file"""
        if not os.path.exists(save_path):
            raise FileNotFoundError(f"Save file '{save_path}' not found.")

        file_size = os.path.getsize(save_path)
        if file_size < MIN_SAVE_FILE_SIZE:
            raise ValueError(
                f"File '{save_path}' is too small ({file_size} bytes) to be "
                f"a valid XCDE save file (minimum {MIN_SAVE_FILE_SIZE} bytes)."
            )

        # Quick sanity check: read the first character's level at the known
        # offset and verify it's within a plausible range for a save file
        try:
            with open(save_path, "rb") as f:
                f.seek(self.PARTY_MEMBERS_OFFSET)
                level_bytes = f.read(4)
                if len(level_bytes) < 4:
                    raise ValueError(
                        "Cannot read character data at expected offset."
                    )
                level = struct.unpack("<I", level_bytes)[0]
                if level > MAX_LEVEL:
                    raise ValueError(
                        f"Data at character offset is unexpected (level={level}). "
                        f"This does not appear to be a valid XCDE save file."
                    )
        except (OSError, struct.error) as e:
            raise ValueError(
                f"Failed to validate save file format: {e}"
            ) from e

    def _ensure_backup(self):
        """Create a backup of the original save file before first modification"""
        if not self._backup_created and not os.path.exists(self.backup_path):
            # Atomic write: write to temp file, then rename
            tmp_path = self.backup_path + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(self.save_data)
            os.replace(tmp_path, self.backup_path)
            print(f"Backup created at {self.backup_path}")
        self._backup_created = True

    def get_character_position(self, character_id):
        """Get the position of a character in the PartyMembers array"""
        char_enum = Character(character_id)
        position = CHARACTER_POSITIONS.get(char_enum)
        if position is None:
            raise ValueError(
                f"Character ID {character_id} does not have a known position "
                f"in the party members array."
            )
        return position

    def _read_member_field(self, character_id, field_offset):
        """Read a 4-byte little-endian field from a character's member block"""
        position = self.get_character_position(character_id)
        offset = (
            self.PARTY_MEMBERS_OFFSET
            + (position * self.PARTY_MEMBER_SIZE)
            + field_offset
        )
        return struct.unpack("<I", self.save_data[offset : offset + 4])[0]

    def _write_member_field(self, character_id, field_offset, value):
        """Write a 4-byte little-endian field to a character's member block"""
        self._ensure_backup()
        position = self.get_character_position(character_id)
        offset = (
            self.PARTY_MEMBERS_OFFSET
            + (position * self.PARTY_MEMBER_SIZE)
            + field_offset
        )
        self.save_data[offset : offset + 4] = struct.pack("<I", value)

    def get_character_exp(self, character_id):
        """Get the current XP for a specific character"""
        return self._read_member_field(character_id, self.EXP_OFFSET_IN_MEMBER)

    def get_character_level(self, character_id):
        """Get the current level for a specific character"""
        return self._read_member_field(character_id, self.LEVEL_OFFSET_IN_MEMBER)

    def get_character_ap(self, character_id):
        """Get the current AP for a specific character"""
        return self._read_member_field(character_id, self.AP_OFFSET_IN_MEMBER)

    def set_character_exp(self, character_id, new_exp):
        """Set a new XP value for a specific character"""
        if new_exp < 0:
            raise ValueError("XP must be a non-negative integer.")
        self._write_member_field(character_id, self.EXP_OFFSET_IN_MEMBER, new_exp)

    def set_character_level(self, character_id, new_level):
        """Set a new level for a specific character"""
        if new_level < 0 or new_level > MAX_LEVEL:
            raise ValueError(f"Level must be between 0 and {MAX_LEVEL}.")
        self._write_member_field(
            character_id, self.LEVEL_OFFSET_IN_MEMBER, new_level
        )

    def set_all_character_levels(self, new_level):
        """Set the same level for all characters (IDs 1-15)"""
        if new_level < 0 or new_level > MAX_LEVEL:
            raise ValueError(f"Level must be between 0 and {MAX_LEVEL}.")
        self._ensure_backup()
        for char_id in range(1, TOTAL_MAIN_CHARACTERS + 1):
            self.set_character_level(char_id, new_level)
        return True

    def set_character_ap(self, character_id, new_ap):
        """Set a new AP value for a specific character"""
        if new_ap < 0:
            raise ValueError("AP must be a non-negative integer.")
        self._write_member_field(character_id, self.AP_OFFSET_IN_MEMBER, new_ap)

    def get_money(self):
        """Get the current money (Gold) amount"""
        return struct.unpack(
            "<I", self.save_data[self.MONEY_OFFSET : self.MONEY_OFFSET + 4]
        )[0]

    def set_money(self, new_money):
        """Set a new money (Gold) amount"""
        self._ensure_backup()
        if new_money < 0 or new_money > MAX_MONEY_VALUE:
            raise ValueError(f"Money must be between 0 and {MAX_MONEY_VALUE}")
        self.save_data[self.MONEY_OFFSET : self.MONEY_OFFSET + 4] = struct.pack(
            "<I", new_money
        )

    def get_art_level(self, art_index):
        """Get the current level of an art"""
        if art_index < 0 or art_index >= self.TOTAL_ARTS:
            raise ValueError(
                f"Art index must be between 0 and {self.TOTAL_ARTS - 1}"
            )
        offset = self.ARTS_LEVELS_OFFSET + (art_index * self.ARTS_LEVEL_SIZE)
        return self.save_data[offset]

    def get_art_max_unlock(self, art_index):
        """Get the max unlock level of an art"""
        if art_index < 0 or art_index >= self.TOTAL_ARTS:
            raise ValueError(
                f"Art index must be between 0 and {self.TOTAL_ARTS - 1}"
            )
        offset = self.ARTS_LEVELS_OFFSET + (art_index * self.ARTS_LEVEL_SIZE) + 1
        return ArtsLevelUnlocked(self.save_data[offset])

    def set_art_level(self, art_index, new_level):
        """Set a new level for an art"""
        self._ensure_backup()
        if art_index < 0 or art_index >= self.TOTAL_ARTS:
            raise ValueError(
                f"Art index must be between 0 and {self.TOTAL_ARTS - 1}"
            )
        if new_level < 0 or new_level > MAX_ART_LEVEL:
            raise ValueError(f"Art level must be between 0 and {MAX_ART_LEVEL}")
        offset = self.ARTS_LEVELS_OFFSET + (art_index * self.ARTS_LEVEL_SIZE)
        self.save_data[offset] = new_level

    def set_art_max_unlock(self, art_index, new_max_unlock):
        """Set a new max unlock level for an art"""
        self._ensure_backup()
        if art_index < 0 or art_index >= self.TOTAL_ARTS:
            raise ValueError(
                f"Art index must be between 0 and {self.TOTAL_ARTS - 1}"
            )
        unlock_value = new_max_unlock
        if not isinstance(unlock_value, int):
            unlock_value = int(ArtsLevelUnlocked(new_max_unlock))
        elif unlock_value < 0 or unlock_value > MAX_ART_UNLOCK:
            raise ValueError(
                f"Max unlock level must be between 0 and {MAX_ART_UNLOCK}"
            )
        offset = self.ARTS_LEVELS_OFFSET + (art_index * self.ARTS_LEVEL_SIZE) + 1
        self.save_data[offset] = unlock_value

    def set_all_arts_levels(self, new_level):
        """Set all arts to the same level"""
        if new_level < 0 or new_level > MAX_ART_LEVEL:
            raise ValueError(f"Art level must be between 0 and {MAX_ART_LEVEL}")
        self._ensure_backup()
        for i in range(self.TOTAL_ARTS):
            self.set_art_level(i, new_level)
        return True

    def set_all_arts_max_unlock(self, new_max_unlock):
        """Set all arts to the same max unlock level"""
        if isinstance(new_max_unlock, int):
            if new_max_unlock < 0 or new_max_unlock > MAX_ART_UNLOCK:
                raise ValueError(
                    f"Max unlock level must be between 0 and {MAX_ART_UNLOCK}"
                )
            unlock_value = new_max_unlock
        else:
            unlock_value = int(ArtsLevelUnlocked(new_max_unlock))
        self._ensure_backup()
        for i in range(self.TOTAL_ARTS):
            self.set_art_max_unlock(i, unlock_value)
        return True

    def save(self, output_path=None, dry_run=False):
        """Save the modified save file.

        Args:
            output_path: Destination path. If None, defaults to save_path + '.modified'.
            dry_run: If True, print what would be written without writing.

        Returns:
            The path where the file was (or would be) saved.
        """
        if output_path is None:
            output_path = self.save_path + ".modified"

        if dry_run:
            print(f"[DRY RUN] Would write modified save to: {output_path}")
            return output_path

        with open(output_path, "wb") as f:
            f.write(self.save_data)
        print(f"Save file written to {output_path}")
        return output_path

    @staticmethod
    def get_character_name(character_id):
        """Get the name of a character from its ID"""
        try:
            return Character(character_id).name
        except ValueError:
            return f"Unknown Character ({character_id})"


# ── CLI Helpers ─────────────────────────────────────────────────────────────────

def display_character_info(editor, character_ids):
    """Display stats for a list of character IDs"""
    print("Character Stats:")
    print("-" * 50)
    for char_id in character_ids:
        try:
            char_name = editor.get_character_name(char_id)
            level = editor.get_character_level(char_id)
            exp = editor.get_character_exp(char_id)
            ap = editor.get_character_ap(char_id)
            print(f"{char_id}: {char_name}")
            print(f"  Level: {level}")
            print(f"  XP: {exp}")
            print(f"  AP: {ap}")
            print("-" * 50)
        except (ValueError, struct.error, OSError):
            pass  # Skip characters that might not be present

    try:
        print(f"Money (Gold): {editor.get_money()}")
        print("-" * 50)
    except (ValueError, struct.error, OSError):
        pass


def adapt_legacy_args(argv=None):
    """Detect and convert legacy positional syntax to new subcommand style.

    Args:
        argv: Argument list to adapt (defaults to sys.argv).

    Separates positional args from flags, detects legacy patterns among the
    positional args, and returns a reconstructed argv list.

    Legacy syntaxes:
      <file>                       → display stats (no change needed)
      <file> <char_id> <xp>        → set-xp
      <file> level <char_id> <lvl> → set-level
      <file> ap <char_id> <ap>     → set-ap
      <file> alllevel <lvl>        → set-all-level
      <file> allartlevel <lvl>     → set-all-art-level
      <file> allartmax <max>       → set-all-art-max
      <file> money <amount>        → set-money

    Flags that take a value (currently just -o/--output) have their value
    consumed as part of the flag, keeping it out of the positional list.

    Returns: adapted sys.argv list (with program name intact).
    """
    if argv is None:
        argv = list(sys.argv)
    if len(argv) < 2:
        return argv  # display mode, no change needed

    # Separate positional args from flags, consuming flag values
    positional = []
    flags = []
    i = 1
    while i < len(argv):
        a = argv[i]
        is_flag = a.startswith("--") or (
            a.startswith("-") and len(a) >= 2 and a != "-"
        )
        if is_flag:
            flags.append(a)
            # -o/--output consumes the next argument as its value
            if a in ("-o", "--output") and i + 1 < len(argv):
                flags.append(argv[i + 1])
                i += 2
                continue
            # Handle -o/path form (no space after -o)
            if a.startswith("-o") and len(a) > 2 and not a.startswith("--"):
                flags[-1] = "-o"
                flags.append(a[2:])
        else:
            positional.append(a)
        i += 1

    # positional[0] = save_file, rest are command + args
    if len(positional) >= 3:
        verb = positional[1]
        if verb in LEGACY_COMMAND_MAP:
            # <file> <legacy_verb> ... → <file> <new_command> ...
            new_cmd = LEGACY_COMMAND_MAP[verb]
            positional[1] = new_cmd
        elif len(positional) == 3:
            # Pure positional: <file> <char_id> <xp> (no verb)
            try:
                int(verb)
                positional.insert(1, "set-xp")
            except ValueError:
                pass  # Not a legacy positional pattern

    return [argv[0]] + positional + flags


def build_argument_parser():
    """Build the command-line argument parser"""
    parser = argparse.ArgumentParser(
        prog="xcde_editor.py",
        description="Xenoblade Chronicles: Definitive Edition Save Editor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Character IDs:\n"
            "  1: SHULK     2: REYN      3: FIORA     4: DUNBAN\n"
            "  5: SHARLA    6: RIKI      7: MELIA     8: FIORA_2\n"
            "  9: DICKSON  10: MUMKHAR  11: ALVIS    12: DUNBAN_2\n"
            " 13: DUNBAN_3 14: KINO     15: NENE\n"
            "\n"
            "Art max unlock values:\n"
            "  0: IV_BEGINNER      (up to level 4)\n"
            "  1: VII_INTERMEDIATE (up to level 7)\n"
            "  2: X_EXPERT         (up to level 10)\n"
            "  3: XII_MASTER       (up to level 12)\n"
            "\n"
            "Legacy syntax is also supported (e.g. '<file> 1 500000' for XP)."
        ),
        add_help=True,
    )

    parser.add_argument(
        "save_file",
        help="Path to the XCDE save file (e.g. bfsgame00.sav)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to disk",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="PATH",
        help="Output path for modified save (default: <save_file>.modified)",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available modification commands (omit to view stats)",
    )

    # --- set-level ---
    p = subparsers.add_parser(
        "set-level", aliases=["sl"],
        help="Set a character's level",
    )
    p.add_argument("character_id", type=int, help="Character ID (1-15)")
    p.add_argument("new_level", type=int, help=f"New level (0-{MAX_LEVEL})")
    _add_shared_opts(p)

    # --- set-all-level ---
    p = subparsers.add_parser(
        "set-all-level", aliases=["sal"],
        help="Set all characters to the same level",
    )
    p.add_argument("new_level", type=int,
                    help=f"New level for all characters (0-{MAX_LEVEL})")
    _add_shared_opts(p)

    # --- set-xp ---
    p = subparsers.add_parser(
        "set-xp", aliases=["sxp"],
        help="Set a character's XP",
    )
    p.add_argument("character_id", type=int, help="Character ID (1-15)")
    p.add_argument("new_xp", type=int, help="New XP value")
    _add_shared_opts(p)

    # --- set-ap ---
    p = subparsers.add_parser(
        "set-ap", aliases=["sap"],
        help="Set a character's AP",
    )
    p.add_argument("character_id", type=int, help="Character ID (1-15)")
    p.add_argument("new_ap", type=int, help="New AP value")
    _add_shared_opts(p)

    # --- set-all-art-level ---
    p = subparsers.add_parser(
        "set-all-art-level", aliases=["saal"],
        help="Set level for ALL arts",
    )
    p.add_argument("new_level", type=int,
                    help=f"Art level (0-{MAX_ART_LEVEL})")
    _add_shared_opts(p)

    # --- set-all-art-max ---
    p = subparsers.add_parser(
        "set-all-art-max", aliases=["saam"],
        help="Set max unlock level for ALL arts",
    )
    p.add_argument("new_max", type=int,
                    help=f"Max unlock level (0-{MAX_ART_UNLOCK})")
    _add_shared_opts(p)

    # --- set-money ---
    p = subparsers.add_parser(
        "set-money", aliases=["sm"],
        help="Set money (Gold)",
    )
    p.add_argument("new_money", type=int,
                    help=f"New money amount (0-{MAX_MONEY_VALUE})")
    _add_shared_opts(p)

    return parser


def _add_shared_opts(p):
    """Add common options (--dry-run, -o/--output) to a subparser."""
    p.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("-o", "--output", default=None, metavar="PATH",
                    help=argparse.SUPPRESS)


def main():
    """Main entry point"""
    # Convert legacy syntax before argparse sees it
    adapted_argv = adapt_legacy_args()
    parser = build_argument_parser()
    args = parser.parse_args(args=adapted_argv[1:])

    save_file = args.save_file
    dry_run = getattr(args, "dry_run", False)
    output_path = getattr(args, "output", None) or (save_file + ".modified")

    # Validate and open the save file
    try:
        editor = XCDESaveEditor(save_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    try:
        if args.command is None:
            # Display mode
            display_character_info(
                editor, range(1, TOTAL_MAIN_CHARACTERS + 1)
            )

        elif args.command in ("set-level", "sl"):
            char_name = editor.get_character_name(args.character_id)
            old = editor.get_character_level(args.character_id)
            editor.set_character_level(args.character_id, args.new_level)
            editor.save(output_path, dry_run=dry_run)
            print(f"Modified {char_name}'s level from {old} to {args.new_level}")

        elif args.command in ("set-all-level", "sal"):
            editor.set_all_character_levels(args.new_level)
            editor.save(output_path, dry_run=dry_run)
            print(f"Set all characters to level {args.new_level}")

        elif args.command in ("set-xp", "sxp"):
            char_name = editor.get_character_name(args.character_id)
            old_xp = editor.get_character_exp(args.character_id)
            old_level = editor.get_character_level(args.character_id)
            editor.set_character_exp(args.character_id, args.new_xp)
            editor.save(output_path, dry_run=dry_run)
            print(f"Modified {char_name}'s XP from {old_xp} to {args.new_xp}")
            print(f"  Current level: {old_level}")
            print("  Note: You may need to adjust the level separately.")

        elif args.command in ("set-ap", "sap"):
            char_name = editor.get_character_name(args.character_id)
            old = editor.get_character_ap(args.character_id)
            editor.set_character_ap(args.character_id, args.new_ap)
            editor.save(output_path, dry_run=dry_run)
            print(f"Modified {char_name}'s AP from {old} to {args.new_ap}")

        elif args.command in ("set-all-art-level", "saal"):
            editor.set_all_arts_levels(args.new_level)
            editor.save(output_path, dry_run=dry_run)
            print(f"Set all arts to level {args.new_level}")

        elif args.command in ("set-all-art-max", "saam"):
            editor.set_all_arts_max_unlock(args.new_max)
            editor.save(output_path, dry_run=dry_run)
            print(f"Set all arts to max unlock level {args.new_max}")

        elif args.command in ("set-money", "sm"):
            old = editor.get_money()
            editor.set_money(args.new_money)
            editor.save(output_path, dry_run=dry_run)
            print(f"Modified money from {old} to {args.new_money}")

    except (ValueError, struct.error, OSError) as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
