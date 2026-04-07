<script lang="ts">
  interface Props {
    models: Record<string, string[]>;
    value: string;
    placeholder?: string;
  }

  let { models, value = $bindable(''), placeholder = 'Type or select a model...' }: Props = $props();

  let inputValue = $state(value);
  let isOpen = $state(false);
  let container: HTMLDivElement;

  // Sync external value changes into input
  $effect(() => {
    inputValue = value;
  });

  // Filtered groups based on case-insensitive substring search
  let filteredGroups = $derived.by(() => {
    const q = inputValue.toLowerCase().trim();
    const result: Record<string, string[]> = {};
    for (const [provider, list] of Object.entries(models)) {
      const matches = q
        ? list.filter(m => m.toLowerCase().includes(q))
        : list;
      if (matches.length) {
        result[provider] = matches;
      }
    }
    return result;
  });

  let hasAnyMatches = $derived(
    Object.values(filteredGroups).some(list => list.length > 0)
  );

  function handleInput(e: Event) {
    inputValue = (e.target as HTMLInputElement).value;
    isOpen = true;
  }

  function handleFocus() {
    isOpen = true;
  }

  function handleBlur(e: FocusEvent) {
    // Delay close so option clicks register first
    setTimeout(() => {
      if (container && !container.contains(document.activeElement)) {
        isOpen = false;
        // Commit current input as the value (supports custom models)
        value = inputValue;
      }
    }, 150);
  }

  function selectOption(option: string) {
    value = option;
    inputValue = option;
    isOpen = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      isOpen = false;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      value = inputValue;
      isOpen = false;
    }
  }

  const providerLabels: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    openrouter: 'OpenRouter',
    google: 'Google',
  };
</script>

<div class="model-picker" bind:this={container}>
  <input
    type="text"
    class="input picker-input"
    {placeholder}
    value={inputValue}
    oninput={handleInput}
    onfocus={handleFocus}
    onblur={handleBlur}
    onkeydown={handleKeydown}
  />
  {#if isOpen}
    <div class="dropdown">
      {#if !Object.keys(models).length}
        <div class="empty-msg">
          No providers configured. Set an API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, or GOOGLE_API_KEY) to see available models.
        </div>
      {:else if !hasAnyMatches}
        <div class="empty-msg">
          No models match "{inputValue}". Press Enter to use this as a custom model.
        </div>
      {:else}
        {#each Object.entries(filteredGroups) as [provider, list]}
          <div class="group">
            <div class="group-header">{providerLabels[provider] || provider}</div>
            {#each list as model}
              <button
                class="option {value === model ? 'selected' : ''}"
                onmousedown={() => selectOption(model)}
                type="button"
              >
                {model}
              </button>
            {/each}
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .model-picker {
    position: relative;
    width: 100%;
    max-width: 420px;
  }
  .picker-input {
    width: 100%;
    font-family: var(--mono, monospace);
    font-size: 13px;
  }
  .dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    max-height: 320px;
    overflow-y: auto;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 6px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    z-index: 100;
    padding: 4px 0;
  }
  .group {
    padding: 4px 0;
  }
  .group:not(:last-child) {
    border-bottom: 1px solid var(--border);
  }
  .group-header {
    padding: 6px 12px 4px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-2);
    font-weight: 600;
  }
  .option {
    display: block;
    width: 100%;
    padding: 6px 12px;
    border: none;
    background: transparent;
    color: var(--text-1);
    font-family: var(--mono, monospace);
    font-size: 12.5px;
    text-align: left;
    cursor: pointer;
    transition: background 0.1s ease;
  }
  .option:hover {
    background: rgba(212, 168, 83, 0.1);
    color: var(--text-0);
  }
  .option.selected {
    background: rgba(212, 168, 83, 0.2);
    color: var(--text-0);
    font-weight: 500;
  }
  .empty-msg {
    padding: 12px 14px;
    font-size: 12px;
    color: var(--text-2);
    line-height: 1.5;
  }
</style>
