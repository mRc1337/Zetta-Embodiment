# Copyright (c) 2026 Zetta Contributors
from __future__ import annotations

import os
import sys
import types
from typing import Any

import pytest

from robots.libero.rlinf_worker_compat import (
    _dispatch_env_call,
    _parent_env_call,
    _pin_pro_render_device,
    compat_worker,
    install_env_call_bridge,
)


class _Nested:
    def combine(self, left: int, *, right: int) -> int:
        return left + right


class _Environment:
    def __init__(self) -> None:
        self.nested = _Nested()
        self.unwrapped = _Nested()

    def combine(self, left: int, *, right: int) -> int:
        return left * right


def test_dispatch_env_call_supports_self_nested_and_unwrapped() -> None:
    environment = _Environment()
    assert _dispatch_env_call(
        environment,
        {"method": "combine", "args": [3], "kwargs": {"right": 4}},
    ) == 12
    assert _dispatch_env_call(
        environment,
        {
            "method": "combine",
            "args": [3],
            "kwargs": {"right": 4},
            "target": "nested",
        },
    ) == 7
    assert _dispatch_env_call(
        environment,
        {
            "method": "combine",
            "args": [3],
            "kwargs": {"right": 4},
            "target": "unwrapped",
        },
    ) == 7


def test_parent_env_call_uses_worker_pipe() -> None:
    class Remote:
        sent: Any = None

        def send(self, value: Any) -> None:
            self.sent = value

        def recv(self) -> str:
            return "reply"

    worker = types.SimpleNamespace(parent_remote=Remote())
    assert _parent_env_call(
        worker,
        "method",
        args=(1,),
        kwargs={"flag": True},
        target="self",
    ) == "reply"
    assert worker.parent_remote.sent == [
        "env_call",
        {
            "method": "method",
            "args": (1,),
            "kwargs": {"flag": True},
            "target": "self",
        },
    ]


def test_pro_render_worker_maps_cuda_to_independent_egl_index(monkeypatch) -> None:
    monkeypatch.setenv("LIBERO_TYPE", "pro")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    monkeypatch.delenv("MUJOCO_EGL_DEVICE_ID", raising=False)
    monkeypatch.setattr("zetta.utils.egl.cuda_to_egl_map", lambda: {0: 1})

    _pin_pro_render_device()

    assert os.environ["CUDA_VISIBLE_DEVICES"] == ""
    assert os.environ["MUJOCO_EGL_DEVICE_ID"] == "1"


def test_pro_render_worker_rejects_wrong_explicit_device(monkeypatch) -> None:
    monkeypatch.setenv("LIBERO_TYPE", "pro")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    monkeypatch.setenv("MUJOCO_EGL_DEVICE_ID", "3")
    monkeypatch.setattr("zetta.utils.egl.cuda_to_egl_map", lambda: {0: 1})

    with pytest.raises(ValueError, match="contradicts CUDA mapping"):
        _pin_pro_render_device()


def test_non_pro_render_worker_keeps_cuda_visibility(monkeypatch) -> None:
    monkeypatch.setenv("LIBERO_TYPE", "standard")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    monkeypatch.delenv("MUJOCO_EGL_DEVICE_ID", raising=False)

    _pin_pro_render_device()

    assert os.environ["CUDA_VISIBLE_DEVICES"] == "3"
    assert "MUJOCO_EGL_DEVICE_ID" not in os.environ


def test_installer_patches_legacy_worker_and_preserves_native(monkeypatch) -> None:
    class LegacyWorker:
        pass

    fake_venv = types.ModuleType("zetta.envs.libero.vector_env")
    fake_venv.ReconfigureSubprocEnvWorker = LegacyWorker
    fake_venv._worker = object()
    fake_libero = types.ModuleType("zetta.envs.libero")
    fake_libero.venv = fake_venv
    monkeypatch.setitem(sys.modules, "zetta.envs.libero", fake_libero)
    monkeypatch.setitem(sys.modules, "zetta.envs.libero.vector_env", fake_venv)

    assert install_env_call_bridge() == "installed"
    assert LegacyWorker.env_call is _parent_env_call
    assert fake_venv._worker is compat_worker
    assert install_env_call_bridge() == "native"
