# llm-wiki

> Memex realized with LLMs.

A Claude Code plugin that turns your knowledge into a wiki the model maintains.
Inspired by [Karpathy's LLM wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Install

```
/plugin install https://github.com/sumin/llm-wiki
```

## Bootstrap your vault

```bash
mkdir -p ~/Vaults/<your-wiki>
cd ~/Vaults/<your-wiki>
claude
> /wiki-init
```

See `commands/` for all available commands.

## License

MIT
