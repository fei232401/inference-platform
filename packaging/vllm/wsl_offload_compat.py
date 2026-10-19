import ctypes

import torch


_runtime = ctypes.CDLL("libcudart.so.13")
_runtime.cudaMemcpyAsync.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_void_p]
_runtime.cudaMemcpyAsync.restype = ctypes.c_int


def select_copy(refs, gpu_to_cpu):
    kind = 2 if gpu_to_cpu else 1

    def copy(src, dst, sizes, is_src_access_order_any=False):
        sources = src.tolist()
        destinations = dst.tolist()
        lengths = sizes.tolist()
        if not len(sources) == len(destinations) == len(lengths):
            raise ValueError("transfer descriptor lengths differ")
        stream = torch.cuda.current_stream()
        for source, destination, length in zip(sources, destinations, lengths):
            if source <= 0 or destination <= 0 or length <= 0:
                raise ValueError("invalid transfer descriptor")
            code = _runtime.cudaMemcpyAsync(destination, source, length, kind, stream.cuda_stream)
            if code:
                raise RuntimeError(f"cudaMemcpyAsync failed with code {code}")

    return copy


class WorkerExtension:
    pass


from vllm.v1.kv_offload.cpu import gpu_worker

gpu_worker._select_swap_blocks_fn = select_copy
