# vllm plugin that adds alpha times a unit vector to the residual stream after one Qwen3.5 decoder layer, re-reading STEER_FILE when it changes.

import json
import logging
import os

import numpy as np
import torch

LOGGER = logging.getLogger(__name__)
STATE: dict = {"mtime": None, "vec": None, "layer": None}


def _refresh(path: str, device: torch.device, dtype: torch.dtype) -> None:
    mtime = os.path.getmtime(path)
    if mtime == STATE["mtime"]:
        return
    cfg = json.loads(open(path).read())
    arr = np.load(cfg["vectors"])
    STATE["layer"] = int(arr["decoder_layer"])
    STATE["vec"] = None if cfg["vector"] == "none" else (torch.tensor(arr[cfg["vector"]]) * float(cfg["alpha"])).to(device, dtype)
    STATE["mtime"] = mtime
    LOGGER.warning(f"steer: layer={STATE['layer']} vector={cfg['vector']} alpha={cfg['alpha']}")


def register() -> None:
    path = os.environ.get("STEER_FILE")
    if not path:
        return
    from vllm.model_executor.models import qwen3_next

    orig = qwen3_next.Qwen3NextDecoderLayer.forward

    def forward(self, *args, **kwargs):
        hidden, residual = orig(self, *args, **kwargs)
        if STATE["layer"] is None or self.layer_idx == STATE["layer"]:
            _refresh(path, hidden.device, hidden.dtype)
        if self.layer_idx == STATE["layer"] and STATE["vec"] is not None:
            hidden = hidden + STATE["vec"]
        return hidden, residual

    qwen3_next.Qwen3NextDecoderLayer.forward = forward
