"""Unit tests for the XCDE save editor.

Run from the repository root with:

    python3 -m unittest discover
"""

import os
import struct
import sys
import tempfile
import unittest

import xcde_editor as e

# Offsets copied from the editor; used only to fabricate a fake save file.
PARTY_MEMBERS_OFFSET = 0x152368
MONEY_OFFSET = 0x151B40


def make_save(path, first_level=10, money=3210):
    """Create a minimal but structurally valid fake save file."""
    data = bytearray(e.MIN_SAVE_FILE_SIZE)
    struct.pack_into("<I", data, PARTY_MEMBERS_OFFSET, first_level)
    struct.pack_into("<I", data, MONEY_OFFSET, money)
    with open(path, "wb") as f:
        f.write(data)
    return path


class SaveValidationTests(unittest.TestCase):
    def test_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                e.XCDESaveEditor(os.path.join(tmp, "missing.sav"))

    def test_rejects_too_small_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "small.sav")
            with open(path, "wb") as f:
                f.write(b"\x00" * 100)
            with self.assertRaises(ValueError):
                e.XCDESaveEditor(path)

    def test_rejects_implausible_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.sav")
            data = bytearray(e.MIN_SAVE_FILE_SIZE)
            struct.pack_into("<I", data, PARTY_MEMBERS_OFFSET, 9999)
            with open(path, "wb") as f:
                f.write(data)
            with self.assertRaises(ValueError):
                e.XCDESaveEditor(path)

    def test_accepts_valid_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "ok.sav"))
            editor = e.XCDESaveEditor(path)
            self.assertEqual(editor.get_character_level(1), 10)


class DryRunTests(unittest.TestCase):
    def test_dry_run_creates_no_backup_and_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            editor = e.XCDESaveEditor(path, dry_run=True)
            editor.set_character_level(1, 50)
            out = editor.save(dry_run=True)
            self.assertFalse(os.path.exists(path + ".backup"))
            self.assertFalse(os.path.exists(out))

    def test_dry_run_memory_changes_but_disk_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            with open(path, "rb") as f:
                original = f.read()
            editor = e.XCDESaveEditor(path, dry_run=True)
            editor.set_money(777)
            editor.save(dry_run=True)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), original)


class WriteTests(unittest.TestCase):
    def test_write_creates_backup_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            with open(path, "rb") as f:
                original = f.read()
            editor = e.XCDESaveEditor(path)
            editor.set_character_level(1, 50)
            self.assertTrue(os.path.exists(path + ".backup"))
            with open(path + ".backup", "rb") as f:
                self.assertEqual(f.read(), original)

    def test_save_writes_modified_data_to_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            out = os.path.join(tmp, "out.sav")
            editor = e.XCDESaveEditor(path)
            editor.set_character_level(1, 50)
            editor.set_money(5000)
            editor.save(out)
            self.assertTrue(os.path.exists(out))
            with open(out, "rb") as f:
                data = f.read()
            self.assertEqual(
                struct.unpack_from("<I", data, PARTY_MEMBERS_OFFSET)[0], 50
            )
            self.assertEqual(struct.unpack_from("<I", data, MONEY_OFFSET)[0], 5000)
            # Original save must be untouched
            with open(path, "rb") as f:
                original_data = f.read()
            self.assertEqual(
                struct.unpack_from("<I", original_data, PARTY_MEMBERS_OFFSET)[0],
                10,
            )

    def test_default_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            editor = e.XCDESaveEditor(path)
            out = editor.save()
            self.assertEqual(out, path + ".modified")
            self.assertTrue(os.path.exists(out))


class ValueValidationTests(unittest.TestCase):
    def test_level_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            editor = e.XCDESaveEditor(path)
            with self.assertRaises(ValueError):
                editor.set_character_level(1, 100)
            with self.assertRaises(ValueError):
                editor.set_character_level(1, -1)

    def test_money_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            editor = e.XCDESaveEditor(path)
            with self.assertRaises(ValueError):
                editor.set_money(-1)
            with self.assertRaises(ValueError):
                editor.set_money(0x100000000)

    def test_art_index_and_level_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            editor = e.XCDESaveEditor(path)
            with self.assertRaises(ValueError):
                editor.set_art_level(0, 13)
            with self.assertRaises(ValueError):
                editor.set_art_level(e.XCDESaveEditor.TOTAL_ARTS, 1)
            with self.assertRaises(ValueError):
                editor.set_art_max_unlock(0, 4)

    def test_invalid_character_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            editor = e.XCDESaveEditor(path)
            with self.assertRaises(ValueError):
                editor.get_character_position(99)

    def test_set_all_levels_sets_every_main_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_save(os.path.join(tmp, "save.sav"))
            editor = e.XCDESaveEditor(path)
            editor.set_all_character_levels(42)
            for char_id in range(1, e.TOTAL_MAIN_CHARACTERS + 1):
                self.assertEqual(editor.get_character_level(char_id), 42)


class MiscTests(unittest.TestCase):
    def test_character_name(self):
        self.assertEqual(e.XCDESaveEditor.get_character_name(1), "SHULK")
        self.assertEqual(
            e.XCDESaveEditor.get_character_name(99), "Unknown Character (99)"
        )

    def test_adapt_legacy_pure_positional_xp(self):
        argv = ["prog", "save.sav", "1", "500000"]
        self.assertEqual(
            e.adapt_legacy_args(argv),
            ["prog", "save.sav", "set-xp", "1", "500000"],
        )

    def test_adapt_legacy_verb_mapping(self):
        argv = ["prog", "save.sav", "level", "2", "99"]
        self.assertEqual(
            e.adapt_legacy_args(argv),
            ["prog", "save.sav", "set-level", "2", "99"],
        )

    def test_adapt_legacy_preserves_flags(self):
        argv = ["prog", "save.sav", "money", "100", "--dry-run"]
        self.assertEqual(
            e.adapt_legacy_args(argv),
            ["prog", "save.sav", "set-money", "100", "--dry-run"],
        )

    def test_adapt_legacy_display_mode_unchanged(self):
        argv = ["prog", "save.sav"]
        self.assertEqual(e.adapt_legacy_args(argv), argv)


if __name__ == "__main__":
    unittest.main()
