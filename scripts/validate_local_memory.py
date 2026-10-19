import hashlib
import json
from pathlib import Path
import tempfile

import torch


def digest(tensor):
    return hashlib.sha256(tensor.contiguous().numpy().tobytes()).hexdigest()


def main():
    torch.set_num_threads(1)
    torch.cuda.set_per_process_memory_fraction(.04)
    expected = torch.arange(256 * 1024, dtype=torch.float32).reshape(256, 1024)
    original_digest = digest(expected)
    gpu = expected.cuda()
    host = torch.empty_like(expected, pin_memory=True)
    host.copy_(gpu, non_blocking=True)
    torch.cuda.synchronize()
    assert host.is_pinned() and digest(host) == original_digest
    del gpu
    torch.cuda.empty_cache()
    restored = host.to("cuda", non_blocking=True)
    torch.cuda.synchronize()
    assert torch.equal(restored.cpu(), expected)
    assert torch.equal((restored * 2 + 3).cpu(), expected * 2 + 3)
    with tempfile.TemporaryDirectory(prefix="fei-memory-probe-") as folder:
        path = Path(folder) / "tensor.pt"
        torch.save(host, path)
        disk = torch.load(path, map_location="cpu", weights_only=True)
        assert digest(disk) == original_digest
        gpu_from_disk = disk.to("cuda")
        assert torch.equal((gpu_from_disk * 2 + 3).cpu(), expected * 2 + 3)
    print(json.dumps({
        "status": "passed", "device": torch.cuda.get_device_name(0),
        "tensor_bytes": expected.numel() * expected.element_size(),
        "sha256": original_digest, "pinned_cpu": host.is_pinned(),
        "checks": ["gpu_to_pinned_cpu_exact", "release_original_gpu_tensor",
                   "cpu_to_gpu_exact", "restored_gpu_computation_exact",
                   "cpu_to_disk_exact", "disk_to_gpu_computation_exact"],
        "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "scope": "1MiB synthetic tensor, not model weights or KV connector validation",
    }), flush=True)


if __name__ == "__main__":
    main()
