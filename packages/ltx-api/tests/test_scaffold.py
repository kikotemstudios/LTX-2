"""Sanity check that fixtures exist."""

from __future__ import annotations

from pathlib import Path


def test_fixtures_exist(fixtures_dir: Path, test_video_path: Path, test_image_path: Path, test_audio_path: Path) -> None:
  assert fixtures_dir.is_dir()
  assert test_video_path.is_file()
  assert test_image_path.is_file()
  assert test_audio_path.is_file()
