INSERT INTO model (name, family, parameter_billions, quantization) VALUES
    ('qwen2.5:0.5b',        'qwen2.5', 0.500, 'q4_k_m'),
    ('qwen2.5:1.5b',        'qwen2.5', 1.500, 'q4_k_m'),
    ('Qwen2.5-7B-Instruct', 'qwen2.5', 7.000, 'none')
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend (name, url, engine, weight, max_concurrency, cost_per_token, state) VALUES
    ('ollama-local', 'http://127.0.0.1:11434',                          'ollama', 1.000,  4, 0.00000000, 'active'),
    ('ollama-k3s',   'http://ollama.ai-platform.svc.cluster.local:11434','ollama', 1.500,  8, 0.00000000, 'active'),
    ('vllm-gpu',     'http://vllm-autodl.ai-platform.svc:8000',          'openai', 3.000, 64, 0.00000200, 'active'),
    ('mock-vllm',    'http://127.0.0.1:11436',                          'openai', 2.000, 16, 0.00000200, 'disabled')
ON CONFLICT (name) DO NOTHING;

INSERT INTO backend_model (backend_id, model_id)
SELECT b.id, m.id
FROM backend b, model m
WHERE (b.name = 'ollama-local' AND m.name IN ('qwen2.5:0.5b', 'qwen2.5:1.5b'))
   OR (b.name = 'ollama-k3s'   AND m.name IN ('qwen2.5:0.5b', 'qwen2.5:1.5b'))
   OR (b.name = 'vllm-gpu'     AND m.name = 'Qwen2.5-7B-Instruct')
   OR (b.name = 'mock-vllm'    AND m.name IN ('qwen2.5:0.5b', 'qwen2.5:1.5b'))
ON CONFLICT DO NOTHING;

INSERT INTO api_key (key_prefix, key_hash, name, scopes, rate_limit_per_second)
VALUES (
    'dev-local-ke',
    '3e90488c475fb2c2997525497f1e72e82dec6d68b5738dc7cebba4371f9f0ee2',
    'local-dev',
    ARRAY['infer', 'admin'],
    10.000
)
ON CONFLICT (key_hash) DO NOTHING;
