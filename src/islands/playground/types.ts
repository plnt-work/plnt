export type Runtime = 'vllm' | 'tgi' | 'trt-llm' | 'sglang';

export type Quantization = 'FP16' | 'FP8' | 'AWQ-4bit' | 'GPTQ-4bit';

export interface ModelVariant {
  quant: Quantization;
  sizeGiB: number;
}

export interface DeployedModel {
  id: string;
  name: string;
  runtime: Runtime;
  runtimeChart: string;
  params: string;
  contextLength: string;
  license: string;
  gpu: string;
  replicas: string;
  variants: ModelVariant[];
  defaultVariant: Quantization;
  description: string;
  briefing: string;
  deployedAgo: string;
  chartVersion: string;
  workflowRun: string;
  endpoint: string;
  manifest: string;
  values: string;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
  ts: number;
}

export type ConnectionState = 'live' | 'stub' | 'checking';
