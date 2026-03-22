"""Real inference backend (config only in CI; GPU smoke optional)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ltx_pipelines")

from ltx_api.config import Settings
from ltx_api.services.real_inference import RealInferenceBackend


def test_real_backend_requires_paths(tmp_path: Path) -> None:
  with pytest.raises(RuntimeError, match="Real backend requires"):
    RealInferenceBackend(
      settings=Settings(
        inference_backend="real",
        checkpoint_path=None,
        gemma_root=None,
        spatial_upsampler_path=None,
      ),
      work_dir=tmp_path,
    )


@pytest.mark.gpu
def test_real_backend_smoke_placeholder() -> None:
  """Full GPU smoke test: set checkpoint env vars and run DistilledPipeline manually."""
  pytest.skip("Opt-in: run with LTX_API_* weights and CUDA")
