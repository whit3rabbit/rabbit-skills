# Write a Service

- 
- Concepts Course
- Plugin Development
- Write a Service
On this page

# Write a Service

**In one sentence**: a service = a named capability hung on `ctx` (`ctx.myService`), which other plugins depend on via `inject: ['myService']`: used to **share logic** across multiple tools/plugins, rather than re-implement it.

This is the page about "sharing capabilities within the process". Tools are for the model; services are for your own code (plugins/tools).

## Contents

- [1. A minimal service](#1-a-minimal-service)
- [2. Service vs tool](#2-service-vs-tool)
- [3. Service injection declaration](#3-service-injection-declaration)
- [4. Service lifecycle hooks and advanced forms](#4-service-lifecycle-hooks-and-advanced-forms)
- [5. Callable services (using a service as a function)](#5-callable-services-using-a-service-as-a-function)
- [6. Consumer-side injection and config override](#6-consumer-side-injection-and-config-override)
- [7. When to use a service](#7-when-to-use-a-service)
- [8. Verification](#8-verification)
- [Next steps](#next-steps)

---

## 1. A minimal service

```ts
import { Context, Service } from '@deepseek-ai/cordis'

export const name = 'my-service'

declare module '@deepseek-ai/cordis' {

  interface Context { myService: MyService }

}

export class MyService extends Service {

  static inject = ['sessions']   // the service's own dependencies

  constructor(ctx: Context) {

    super(ctx, 'myService')

  }

  async summarize(sessionId: string): Promise<string> {

    return '...'   // real logic: read the session, call the llm, return a summary

  }

}

export async function apply(ctx: Context) {

  await ctx.plugin(MyService)   // await is optional (see below)

}
```

## 2. Service vs tool

|  | Tool | Service |
| --- | --- | --- |
| Who uses it | model | plugins (same process) |
| Entry point | ctx.tools.register | ctx.plugin(ServiceClass) |
| Dependency | inject: ['tools'] | inject: ['myService'] |
| Capability | single execution | arbitrary method set |

**Typical pattern: the service implements the logic, the tool is a thin shell**

```ts
ctx.tools.register({

  name: 'my_summarize',

  parameters: { sessionId: { type: 'string' } },

  output: { schema: { type: 'string' }, render: (_a, v) => [{ type: 'text', text: String(v) }] },

  execute: ({ sessionId }) => ctx.myService.summarize(sessionId),

})
```

## 3. Service injection declaration

```ts
export const inject = ['myService']   // undeclared access → Proxy rejection (capability-based)
```

A consumer either declares it in `inject` (function style) / `static inject` (class style), or uses `ctx.inject(['x'], cb)` to take it asynchronously.

## 4. Service lifecycle hooks and advanced forms

| Hook/symbol | Role |
| --- | --- |
| [Service.init] | async init after construction (await load/publish) |
| [Service.check] | availability predicate (used by fiber refresh) |
| [Service.config] / resolveConfig | merges ancestor intercept config |
| [Service.filter] | isolate scope boundary |
| [Service.invoke] | wraps the service into a callable object (ctx.logger() style) |
| [Service.tracker] | binds the caller |
| @Inject decorator | class-property injection |

**Dependency declaration**: a class plugin's dependencies are read from `static inject` and normalized through `Inject.resolve`, which are **not the same source** as `apply`'s `inject`. `await ctx.plugin(MyService)` returns the fiber's thenable; **await is optional**: its value is guaranteeing that the fiber reaches ACTIVE and throws boot/config errors.

## 5. Callable services (using a service as a function)

If a service defines `[Service.invoke]`, the constructor wraps it into a callable object: use `ctx.myService(...)` like `ctx.logger()`:

```ts
export class Logger extends Service {

  get [Service.invoke]() {

    return (msg: string) => this.log(msg)

  }

  log(msg: string) { ... }

}

// consumer: ctx.logger('hello')  —— not ctx.logger.log('hello')
```

## 6. Consumer-side injection and config override

| Way | Role |
| --- | --- |
| ctx.inject(['x'], cb) | async injection (take x in cb before using it) |
| ctx.get | injection bypass |
| ctx.intercept(name, config) | flows into Service.resolveConfig, overrides the service config |

## 7. When to use a service

| Scenario | Use a service |
| --- | --- |
| Several tools/plugins share the same logic | ✅ the service implements it, tools call it |
| A capability is reused across sessions/agents | ✅ |
| Give the model a new capability | ❌ use a tool |
| Just one internal function of this plugin | ❌ a service is unnecessary |

Rule of thumb: if you catch yourself writing two tools that do the same thing, extract it into a service + two thin-shell tools.

## 8. Verification

```sh
# The service is visible in the composition tree

dsh web --dump-config | grep -A2 my-service
```

## Next steps

- [Listen to events](../../learn/dev/listen-events.md): services responding to session changes

- [Configuration and publishing](../../learn/dev/config-publish.md): making services/plugins configurable
