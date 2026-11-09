# Experimental Plugin Record Catalog

These current-source PluginRecordMap declarations describe ignorable, log-only records owned by experimental packages. Payload annotations link to their owning source without expanding referenced types. Records stay outside the known-event set, persistence schema fingerprints, and compatibility history; format migrations retain them on a best-effort basis.

Run `pnpm run gen-persistence-catalog` to regenerate both persistence catalogs, their language pairs, and associated artifacts. `pnpm run verify-persistence-catalog` checks all generated files.

Shared Session event declarations and resolved schemas appear in the [Session persistence event catalog](./persistence-catalog.md).

| Record | Owner | Purpose | Payload and source |
| --- | --- | --- | --- |
| plugin:translator/request | @deepseek-ai/dsh-experimental-translator | Provider-independent translation input, retained before dispatch. | TranslationRequestRecord · packages/experimental/translator/src/types.ts |
| plugin:translator/result | @deepseek-ai/dsh-experimental-translator | Successful translation, retained before it is returned to the consumer. | TranslationResultRecord · packages/experimental/translator/src/types.ts |
