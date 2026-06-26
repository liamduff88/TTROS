# Hermes Portal: tools-only path

The audited AgenticOSClean inference provider is `openai-codex`. Portal OAuth is
permitted only for Tool Gateway capabilities and must not change that provider.

1. Run `tools/hermes_portal_tools_only.sh --prepare` in AgenticOSClean.
2. Run `hermes tools` manually.
3. Choose only **Tool Gateway / Nous Subscription** for **Web Search & Extract**
   or **Firecrawl**. Other Portal-backed tools (image or TTS) may be enabled only
   when deliberately required.
4. Run `tools/hermes_portal_tools_only.sh --verify` immediately afterward.

Do not run `hermes setup --portal`, bare `hermes portal`, or `hermes model`.
Those onboarding/model flows can select Nous as the inference provider. The safe
tools-only flow is `hermes tools`; a successful verification reports the model
provider unchanged and model takeover `no`.
