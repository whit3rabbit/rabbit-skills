# Testing a DSH extension

Offline notes from the pinned upstream testing policy. Choose checks that demonstrate the behavior users depend on.

## Test the composition and the result

- Verify manifest and source structure, then load through the actual Loader in an isolated composition.
- For a tool, inspect the registered schema and assert the canonical result and the model-facing content. Try valid input, rejected input, and unload.
- For a skill, inspect the session catalog and invocation trace. Include a nearby prompt that should skip the skill and a user gesture that should load it once.
- Keep the tool registry, dispatch, and persistence real when using a scripted model. Replace external or nondeterministic boundaries such as the model API.
- Check the workspace or resulting artifact outside the agent transcript. A success claim in the final response cannot prove that the tool or skill behaved correctly.

[Upstream testing policy](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/docs/testing.md)
