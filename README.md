
<p align="center"><code>npm i -g @openai/tunacode</code><br />or <code>brew install tunacode</code></p>

<p align="center"><strong>Tunacode CLI</strong> is a coding agent from OpenAI that runs locally on your computer.
</br>
</br>If you want tunacode in your code editor (VS Code, Cursor, Windsurf), <a href="https://developers.openai.com/tunacode/ide">install in your IDE</a>
</br>If you are looking for the <em>cloud-based agent</em> from OpenAI, <strong>tunacode Web</strong>, go to <a href="https://chatgpt.com/tunacode">chatgpt.com/tunacode</a></p>

<p align="center">
  <img src="./.github/tunacode-cli-splash.png" alt="tunacode CLI splash" width="80%" />
  </p>

---

## Quickstart

### Installing and running tunacode CLI

Install globally with your preferred package manager. If you use npm:

```shell
npm install -g @openai/tunacode
```

Alternatively, if you use Homebrew:

```shell
brew install tunacode
```

Then simply run `tunacode` to get started:

```shell
tunacode
```

<details>
<summary>You can also go to the <a href="https://github.com/openai/tunacode/releases/latest">latest GitHub Release</a> and download the appropriate binary for your platform.</summary>

Each GitHub Release contains many executables, but in practice, you likely want one of these:

- macOS
  - Apple Silicon/arm64: `tunacode-aarch64-apple-darwin.tar.gz`
  - x86_64 (older Mac hardware): `tunacode-x86_64-apple-darwin.tar.gz`
- Linux
  - x86_64: `tunacode-x86_64-unknown-linux-musl.tar.gz`
  - arm64: `tunacode-aarch64-unknown-linux-musl.tar.gz`

Each archive contains a single entry with the platform baked into the name (e.g., `tunacode-x86_64-unknown-linux-musl`), so you likely want to rename it to `tunacode` after extracting it.

</details>

### Using tunacode with your ChatGPT plan

<p align="center">
  <img src="./.github/tunacode-cli-login.png" alt="tunacode CLI login" width="80%" />
  </p>

Run `tunacode` and select **Sign in with ChatGPT**. We recommend signing into your ChatGPT account to use tunacode as part of your Plus, Pro, Team, Edu, or Enterprise plan. [Learn more about what's included in your ChatGPT plan](https://help.openai.com/en/articles/11369540-tunacode-in-chatgpt).

You can also use tunacode with an API key, but this requires [additional setup](./docs/authentication.md#usage-based-billing-alternative-use-an-openai-api-key). If you previously used an API key for usage-based billing, see the [migration steps](./docs/authentication.md#migrating-from-usage-based-billing-api-key). If you're having trouble with login, please comment on [this issue](https://github.com/openai/tunacode/issues/1243).

### Model Context Protocol (MCP)

tunacode CLI supports [MCP servers](./docs/advanced.md#model-context-protocol-mcp). Enable by adding an `mcp_servers` section to your `~/.tunacode/config.toml`.


### Configuration

tunacode CLI supports a rich set of configuration options, with preferences stored in `~/.tunacode/config.toml`. For full configuration options, see [Configuration](./docs/config.md).

---

### Docs & FAQ

- [**Getting started**](./docs/getting-started.md)
  - [CLI usage](./docs/getting-started.md#cli-usage)
  - [Running with a prompt as input](./docs/getting-started.md#running-with-a-prompt-as-input)
  - [Example prompts](./docs/getting-started.md#example-prompts)
  - [Memory with AGENTS.md](./docs/getting-started.md#memory-with-agentsmd)
  - [Configuration](./docs/config.md)
- [**Sandbox & approvals**](./docs/sandbox.md)
- [**Authentication**](./docs/authentication.md)
  - [Auth methods](./docs/authentication.md#forcing-a-specific-auth-method-advanced)
  - [Login on a "Headless" machine](./docs/authentication.md#connecting-on-a-headless-machine)
- [**Advanced**](./docs/advanced.md)
  - [Non-interactive / CI mode](./docs/advanced.md#non-interactive--ci-mode)
  - [Tracing / verbose logging](./docs/advanced.md#tracing--verbose-logging)
  - [Model Context Protocol (MCP)](./docs/advanced.md#model-context-protocol-mcp)
- [**Zero data retention (ZDR)**](./docs/zdr.md)
- [**Contributing**](./docs/contributing.md)
- [**Install & build**](./docs/install.md)
  - [System Requirements](./docs/install.md#system-requirements)
  - [DotSlash](./docs/install.md#dotslash)
  - [Build from source](./docs/install.md#build-from-source)
- [**FAQ**](./docs/faq.md)
- [**Open source fund**](./docs/open-source-fund.md)

---

## License

This repository is licensed under the [Apache-2.0 License](LICENSE).
