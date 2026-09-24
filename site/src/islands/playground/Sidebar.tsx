import type { DeployedModel, Quantization } from './types';
import { MODELS, RUNTIME_LABEL } from './models';

interface Props {
  model: DeployedModel;
  variant: Quantization;
  onSelectModel: (id: string) => void;
  onSelectVariant: (q: Quantization) => void;
  onStart: () => void;
}

export default function Sidebar({ model, variant, onSelectModel, onSelectVariant, onStart }: Props) {
  const activeVariant = model.variants.find((v) => v.quant === variant) ?? model.variants[0];
  return (
    <aside class="pg-sidebar">
      <div class="pg-sidebar-inner">
        <div class="pg-block">
          <div class="pg-label">Model</div>
          <select
            class="pg-model-select"
            value={model.id}
            onChange={(e) => onSelectModel((e.currentTarget as HTMLSelectElement).value)}
            aria-label="Deployed model"
          >
            {MODELS.map((m) => (
              <option value={m.id}>{m.name}</option>
            ))}
          </select>
          <div class="pg-sub">{RUNTIME_LABEL[model.runtime]} · {model.gpu} · {model.params}</div>
        </div>

        <p class="pg-desc">{model.description}</p>

        <div class="pg-block">
          <div class="pg-label">Quantization</div>
          <select
            class="pg-variant-select"
            value={variant}
            onChange={(e) => onSelectVariant((e.currentTarget as HTMLSelectElement).value as Quantization)}
            aria-label="Model quantization"
          >
            {model.variants.map((v) => (
              <option value={v.quant}>{v.quant} · {v.sizeGiB} GiB</option>
            ))}
          </select>
        </div>

        <button class="pg-cta" onClick={onStart}>
          New session <span class="pg-cta-arrow">→</span>
        </button>

        <dl class="pg-meta">
          <div><dt>Context</dt><dd>{model.contextLength}</dd></div>
          <div><dt>License</dt><dd>{model.license}</dd></div>
          <div><dt>Selected</dt><dd>{activeVariant.quant} · {activeVariant.sizeGiB} GiB</dd></div>
          <div><dt>Deployed</dt><dd>{model.deployedAgo} ago</dd></div>
          <div><dt>Chart</dt><dd class="pg-mono">{model.chartVersion}</dd></div>
        </dl>

        <p class="pg-footnote">
          Sessions live in memory — refresh clears them.
          Point clients at your own plnt endpoint via <code>PUBLIC_PLNT_ENDPOINT</code>.
        </p>
      </div>
    </aside>
  );
}
