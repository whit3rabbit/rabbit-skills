# Service

The base class for context services. A subclass loaded as a plugin registers itself as `ctx.<name>`.

Base class for services that expose a named API on `ctx`.

Subclasses call `super(ctx, name)` from their constructor. The service is registered immediately and is automatically removed with the owning fiber.

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L11)

### service.name

```ts
/** The service name this instance is registered under. */
public name!: string
```

The service name this instance is registered under.

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L30)

## Static members

### Service.init

```ts
/** Symbol key of an instance method run after construction (class plugins). */
static readonly init: unique symbol
```

Symbol key of an instance method run after construction (class plugins).

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L13)

### Service.check

```ts
/** Symbol key of the availability predicate passed to `ctx.provide()`. */
static readonly check: unique symbol
```

Symbol key of the availability predicate passed to `ctx.provide()`.

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L15)

### Service.config

```ts
/** Symbol key of the phantom intercept-config type parameter. */
static readonly config: unique symbol
```

Symbol key of the phantom intercept-config type parameter.

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L17)

### Service.invoke

```ts
/** Symbol key of the call body making a service callable (e.g. `ctx.logger()`). */
static readonly invoke: unique symbol
```

Symbol key of the call body making a service callable (e.g. `ctx.logger()`).

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L19)

### Service.extend

```ts
/** Symbol key of the helper deriving an extended service instance. */
static readonly extend: unique symbol
```

Symbol key of the helper deriving an extended service instance.

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L21)

### Service.tracker

```ts
/** Symbol key of the tracker metadata used for context tracing. */
static readonly tracker: unique symbol
```

Symbol key of the tracker metadata used for context tracing.

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L23)

### Service.resolveConfig

```ts
/** Symbol key of the intercept-config resolution helper below. */
static readonly resolveConfig: unique symbol
```

Symbol key of the intercept-config resolution helper below.

[Source](https://github.com/deepseek-ai/deepseek-harness/blob/master/vendor/cordis/src/service.ts#L25)
