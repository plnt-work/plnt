import type { DeployedModel } from './types';

const LLAMA_MANIFEST = `apiVersion: plnt.work/v1
kind: InferenceModel
metadata:
  name: llama-3.1-70b-instruct
spec:
  runtime: vllm
  model:
    name: meta-llama/Llama-3.1-70B-Instruct
    storageUri: s3://plnt-models/llama-3.1-70b/fp16
    quantization: fp16
  resources:
    gpu: 2
    gpuClass: nvidia.com/h100
    memoryGiB: 160
  replicas:
    min: 1
    max: 4
  canary:
    trafficPercent: 5
  # In production plnt runs this on a real GPU node.
  # In the demo playground, requests are proxied to NVIDIA NIM hosted API
  # so you can talk to the actual model without owning the hardware.
`;

const LLAMA_VALUES = `image:
  repository: vllm/vllm-openai
  tag: v0.6.3
model:
  name: meta-llama/Llama-3.1-70B-Instruct
  storageUri: s3://plnt-models/llama-3.1-70b/fp16
runtime:
  args:
    - --tensor-parallel-size=2
    - --max-model-len=8192
    - --gpu-memory-utilization=0.90
    - --enable-prefix-caching
resources:
  limits:
    nvidia.com/gpu: 2
`;

const NEMOTRON_MANIFEST = `apiVersion: plnt.work/v1
kind: InferenceModel
metadata:
  name: nemotron-70b-instruct
spec:
  runtime: trt-llm
  model:
    name: nvidia/Llama-3.1-Nemotron-70B-Instruct
    storageUri: s3://plnt-models/nemotron-70b/trt-fp8
    quantization: fp8
  resources:
    gpu: 4
    gpuClass: nvidia.com/a100
  replicas:
    min: 1
    max: 2
`;

const NEMOTRON_VALUES = `image:
  repository: nvcr.io/nvidia/tritonserver
  tag: 24.09-trtllm-python-py3
runtime:
  args:
    - --world_size=4
    - --engine_dir=/engines/nemotron-70b-fp8
resources:
  limits:
    nvidia.com/gpu: 4
`;

const MIXTRAL_MANIFEST = `apiVersion: plnt.work/v1
kind: InferenceModel
metadata:
  name: mixtral-8x22b-instruct
spec:
  runtime: tgi
  model:
    name: mistralai/Mixtral-8x22B-Instruct-v0.1
    storageUri: s3://plnt-models/mixtral-8x22b/fp16
    quantization: fp16
  resources:
    gpu: 4
    gpuClass: nvidia.com/h100
  replicas:
    min: 1
    max: 3
`;

const MIXTRAL_VALUES = `image:
  repository: ghcr.io/huggingface/text-generation-inference
  tag: 2.3.1
model:
  name: mistralai/Mixtral-8x22B-Instruct-v0.1
runtime:
  args:
    - --num-shard=4
    - --max-input-length=16384
    - --max-total-tokens=32768
resources:
  limits:
    nvidia.com/gpu: 4
`;

const DEEPSEEK_MANIFEST = `apiVersion: plnt.work/v1
kind: InferenceModel
metadata:
  name: deepseek-r1
spec:
  runtime: sglang
  model:
    name: deepseek-ai/DeepSeek-R1
    storageUri: s3://plnt-models/deepseek-r1/fp8
    quantization: fp8
  resources:
    gpu: 8
    gpuClass: nvidia.com/h100
  replicas:
    min: 1
    max: 2
`;

const DEEPSEEK_VALUES = `image:
  repository: lmsysorg/sglang
  tag: v0.3.4-cu121
runtime:
  args:
    - --tp=8
    - --context-length=32768
    - --enable-torch-compile
resources:
  limits:
    nvidia.com/gpu: 8
`;

export const MODELS: DeployedModel[] = [
  {
    id: 'llama-3.1-70b-instruct',
    name: 'llama-3.1-70b-instruct',
    runtime: 'vllm',
    runtimeChart: 'vllm-runtime-0.3.1',
    params: '70B',
    contextLength: '128k',
    license: 'Llama 3.1 Community',
    gpu: '2×H100',
    replicas: '1–4',
    variants: [
      { quant: 'FP16', sizeGiB: 141 },
      { quant: 'FP8', sizeGiB: 75 },
      { quant: 'AWQ-4bit', sizeGiB: 38 },
    ],
    defaultVariant: 'FP16',
    description:
      'Meta Llama 3.1 70B instruction-tuned. In the demo playground, requests are proxied to NVIDIA NIM. The InferenceModel manifest below is what runs when you self-host on a GPU cluster.',
    briefing:
      'Llama 3.1 70B is the default general-purpose model. In the plnt playground your prompt travels: browser → playground.plnt.work (FastAPI proxy on Fly.io) → NVIDIA NIM hosted API → model → back. On a real GPU cluster, the exact same InferenceModel manifest would deploy this via the vLLM Helm chart instead.',
    deployedAgo: '3h 12m',
    chartVersion: 'vllm-runtime-0.3.1',
    workflowRun: 'r-9c4f218e0a',
    endpoint: 'https://playground.plnt.work/v1/chat/completions',
    manifest: LLAMA_MANIFEST,
    values: LLAMA_VALUES,
  },
  {
    id: 'nemotron-70b-instruct',
    name: 'nemotron-70b-instruct',
    runtime: 'trt-llm',
    runtimeChart: 'trt-llm-runtime-0.1.0',
    params: '70B',
    contextLength: '128k',
    license: 'Llama 3.1 Community',
    gpu: '4×A100',
    replicas: '1–2',
    variants: [
      { quant: 'FP8', sizeGiB: 70 },
      { quant: 'AWQ-4bit', sizeGiB: 38 },
    ],
    defaultVariant: 'FP8',
    description:
      'NVIDIA\'s Llama-3.1-Nemotron-70B — RLHF-tuned Llama with strong reasoning benchmarks. Compiled to a TensorRT-LLM engine on Triton. Playground proxies to NIM hosted API.',
    briefing:
      'Nemotron 70B is NVIDIA\'s post-trained Llama 3.1 variant. The plnt platform builds the TRT-LLM engine as a workflow step during deploy — cold-start ~7 min, warm ~40 s. In the demo playground you\'re hitting NVIDIA\'s hosted NIM directly; self-hosting would go through the trt-llm-runtime chart.',
    deployedAgo: '1d 4h',
    chartVersion: 'trt-llm-runtime-0.1.0',
    workflowRun: 'r-88fe0c3b2d',
    endpoint: 'https://playground.plnt.work/v1/chat/completions',
    manifest: NEMOTRON_MANIFEST,
    values: NEMOTRON_VALUES,
  },
  {
    id: 'mixtral-8x22b-instruct',
    name: 'mixtral-8x22b-instruct',
    runtime: 'tgi',
    runtimeChart: 'tgi-runtime-0.2.4',
    params: '141B (MoE)',
    contextLength: '64k',
    license: 'Apache-2.0',
    gpu: '4×H100',
    replicas: '1–3',
    variants: [
      { quant: 'FP16', sizeGiB: 262 },
      { quant: 'AWQ-4bit', sizeGiB: 74 },
    ],
    defaultVariant: 'FP16',
    description:
      'Mixtral 8×22B — sparse MoE, 39B active params per token. Served via Hugging Face TGI. Playground proxies to NIM hosted API.',
    briefing:
      'Mixtral 8×22B is a Mixture-of-Experts model — only 2 of 8 experts activate per token, so effective compute is closer to a 39B dense model. TGI handles the expert routing internally. On real GPUs plnt runs this via the tgi-runtime chart with num_shard=4.',
    deployedAgo: '6h 41m',
    chartVersion: 'tgi-runtime-0.2.4',
    workflowRun: 'r-4d8b2e9017',
    endpoint: 'https://playground.plnt.work/v1/chat/completions',
    manifest: MIXTRAL_MANIFEST,
    values: MIXTRAL_VALUES,
  },
  {
    id: 'deepseek-r1',
    name: 'deepseek-r1',
    runtime: 'sglang',
    runtimeChart: 'sglang-runtime-0.1.2',
    params: '671B (MoE)',
    contextLength: '128k',
    license: 'MIT',
    gpu: '8×H100',
    replicas: '1–2',
    variants: [
      { quant: 'FP8', sizeGiB: 671 },
      { quant: 'AWQ-4bit', sizeGiB: 200 },
    ],
    defaultVariant: 'FP8',
    description:
      'DeepSeek-R1 — reasoning model with chain-of-thought training, 37B active params per token. Served via SGLang. Playground proxies to NIM hosted API.',
    briefing:
      'DeepSeek-R1 is a reasoning-focused model that emits <think>...</think> traces before its final answer. SGLang\'s RadixAttention gives strong prefix-cache hit rates for the long reasoning chains. On real GPUs it needs 8×H100 with TP=8.',
    deployedAgo: '2d 9h',
    chartVersion: 'sglang-runtime-0.1.2',
    workflowRun: 'r-71a2f04c1e',
    endpoint: 'https://playground.plnt.work/v1/chat/completions',
    manifest: DEEPSEEK_MANIFEST,
    values: DEEPSEEK_VALUES,
  },
];

export const RUNTIME_LABEL: Record<string, string> = {
  vllm: 'vLLM',
  tgi: 'TGI',
  'trt-llm': 'TRT-LLM',
  sglang: 'SGLang',
};
