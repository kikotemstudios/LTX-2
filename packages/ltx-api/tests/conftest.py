"""Pytest fixtures for ltx-api."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
  return FIXTURES_DIR


@pytest.fixture
def test_video_path(fixtures_dir: Path) -> Path:
  return fixtures_dir / "test_video.mp4"


@pytest.fixture
def test_image_path(fixtures_dir: Path) -> Path:
  return fixtures_dir / "test_image.png"


@pytest.fixture
def test_audio_path(fixtures_dir: Path) -> Path:
  return fixtures_dir / "test_audio.wav"
