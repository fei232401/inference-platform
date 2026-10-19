import ctypes
import importlib.util
from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def adapter(monkeypatch):
    calls = []

    class Copy:
        code = 0

        def __call__(self, *args):
            calls.append(args)
            return self.code

    copy = Copy()
    monkeypatch.setattr(ctypes, "CDLL", lambda name: types.SimpleNamespace(cudaMemcpyAsync=copy))
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(current_stream=lambda: types.SimpleNamespace(cuda_stream=123))
    monkeypatch.setitem(sys.modules, "torch", torch)
    for name in ["vllm", "vllm.v1", "vllm.v1.kv_offload", "vllm.v1.kv_offload.cpu"]:
        package = types.ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    worker = types.ModuleType("vllm.v1.kv_offload.cpu.gpu_worker")
    monkeypatch.setitem(sys.modules, worker.__name__, worker)
    spec = importlib.util.spec_from_file_location("wsl_offload_test", Path(__file__).parents[1] / "packaging/vllm/wsl_offload_compat.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert worker._select_swap_blocks_fn is module.select_copy
    return module, calls, copy


def tensor(values):
    return types.SimpleNamespace(tolist=lambda: values)


@pytest.mark.parametrize("gpu_to_cpu,kind", [(True, 2), (False, 1)])
def test_copy_preserves_direction_offsets_and_stream(adapter, gpu_to_cpu, kind):
    module, calls, _ = adapter
    module.select_copy([], gpu_to_cpu)(tensor([100, 200]), tensor([300, 400]), tensor([16, 32]))
    assert calls == [(300, 100, 16, kind, 123), (400, 200, 32, kind, 123)]


def test_runtime_error_is_not_silenced(adapter):
    module, _, copy = adapter
    copy.code = 2
    with pytest.raises(RuntimeError, match="code 2"):
        module.select_copy([], True)(tensor([100]), tensor([200]), tensor([16]))


def test_invalid_pointer_is_rejected(adapter):
    module, calls, _ = adapter
    with pytest.raises(ValueError, match="invalid transfer"):
        module.select_copy([], True)(tensor([0]), tensor([200]), tensor([16]))
    assert not calls


def test_descriptor_lengths_must_match(adapter):
    module, calls, _ = adapter
    with pytest.raises(ValueError, match="lengths differ"):
        module.select_copy([], True)(tensor([100]), tensor([]), tensor([16]))
    assert not calls
