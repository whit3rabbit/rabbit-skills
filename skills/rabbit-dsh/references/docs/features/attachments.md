# Attachments

**Source update (`0.1.5-alpha.1`)**: since 0.1.3-alpha.1 the Web UI accepts uploads of arbitrary file types — files and images share one draft attachment rail, background uploads expose progress and cancellation and stay visible across conversation switches, and the model reads saved read-only paths on demand instead of receiving file bytes. The image path still carries identity, dimensions, media type, normalization warnings, and a read-only execution-world path; copy to a writable path before editing, and durable references remain content-addressed. Request bytes are route-specific cached projections, not arbitrary host paths. Source: `packages/attachment/attachment`, `packages/attachment/attachment-local`, `packages/client/ui-attachment`, and `packages/fs/tool-fs/src/read-image.ts`.

**In one sentence**: `ctx.attachments` is a **persistent binary attachment seam**: it validates and atomically commits immutable image bytes and generic file bytes, returning a serializable `ImageAttachmentRef` or `FileAttachmentRef`. `attachment-local` is its local filesystem implementation, and `ui-attachment` is the pure React attachment atom.

Unsent browser drafts do not live here; bytes only enter persistent storage when the user submits a prompt or a provider adapter submits structured model output.

## Contents

- [1. What it is](#1-what-it-is)
- [2. Reference and write API (attachment)](#2-reference-and-write-api-attachment)
- [3. Local storage (attachment-local)](#3-local-storage-attachment-local)
- [4. Browser UI atom (ui-attachment)](#4-browser-ui-atom-ui-attachment)
- [5. Configuration](#5-configuration)
- [6. Known limitations](#6-known-limitations)
- [7. Verification](#7-verification)
- [Next steps](#next-steps)

---

## 1. What it is

The attachment capability solves one thing: **persist** image and generic file bytes so that session logs only keep a **content-addressed reference + validated metadata**, not browser paths, object URLs, provider URLs, or base64. Both core packages are product packages.

| Package | ctx key | Role |
| --- | --- | --- |
| attachment | ctx.attachments | Immutable image/file references, image limits, storage service |
| attachment-local | (registered on ctx.attachments) | Content-addressed private storage under DSH_HOME |
| ui-attachment | none (pure presentation layer) | Pure React attachment atom: mixed draft rail, history gallery, large-image lightbox |

## 2. Reference and write API (attachment)

`ctx.attachments` validates and atomically commits immutable image bytes and generic file bytes, returning a serializable `ImageAttachmentRef` or `FileAttachmentRef`; consumers **never** persist browser paths, object URLs, provider URLs, or base64 into session events.

- `validateImage`: runs the same admission policy but **does not persist**

- `saveImages` (rc.7): **ordered batch commit** — validates every member before writing any; admission failures start no writes, storage failures return no partial references (already-published content-addressed objects may remain until a future retention policy collects them)

- `saveImage`: commits every accepted image **before** each model-visible session event is published

- `readImage`: validates the content-addressed object against recorded metadata; the caller can cancel, the implementation observes the cancellation and preserves it as a cancellation (not translated into a storage failure)

- `saveFile` / `saveFileStream`: commit an existing byte array / bounded chunks with backpressure and cancellation; both file write paths impose **no admission limits** and store bytes verbatim

- `readFileStream` / `fileHostPath`: verified bounded chunk reads / locate the stored object for read-only on-demand projection

- `admitEncodedFile` and `admitPromptContent`: encoded-file admission; a Host prompt consumer hands ordered text, encoded images, and resolved file references to `ctx.attachments.admitPromptContent()`

- `isAttachmentError`: recognize attachment errors and route by `code` instead of the prototype chain

Unsent composer images and files remain temporary browser-owned drafts.

Web prompt admission (`packages/api/session-controller`) rejects a message with neither **non-whitespace text** nor an attachment (0.1.5); image-only and file-only messages remain valid, and blank queue edits are rejected too.

## 3. Local storage (attachment-local)

`attachment-local` is the private local implementation of `attachment`, **mounted by default** (base composition).

- Image objects live at `<DSH_HOME>/attachments/v1/objects/<sha256-prefix>/<sha256>`, addressed by an opaque `sha256:` id

- The single canonical object for generic file bytes lives at `<DSH_HOME>/attachments/v1/file-objects/<digest-prefix>/<digest>`; every reference path `<DSH_HOME>/attachments/v1/files/<digest-prefix>/<digest>/<name>` is a read-only hard link, so files with different names but identical bytes never duplicate disk usage

- Each process syncs home-directory ancestors step by step to the filesystem root, proving the home directory is **durable only once**, avoiding mistaking "a directory another process created but has not yet synced" for a safe boundary

- Writes use a private staging directory, owner-only files, synced temporary files, atomic exclusive hard-link publication, and directory syncing on the publish path (POSIX; Windows relies on filesystem metadata journaling), ensuring the reported reference survives crashes

- Image write admission and reads **fully decode the raster** before accepting format and dimensions; files are stored verbatim with no admission limits, and reads verify the full digest and recorded byte count

- `DSH_HOME` follows the shared path policy: explicit config → `$DSH_HOME` → `~/.dsh`. Session logs contain only references and validated metadata, **never this host path**

- `readImage` forwards an optional cancellation into the filesystem read and preserves the cancellation rather than wrapping it as `ATTACHMENT_READ_FAILED`

- Generic file bytes **never reach a provider request**: every route receives one deterministic handle line naming the file identity and read-only process path; when the execution world cannot map it, the handle says so

## 4. Browser UI atom (ui-attachment)

A pure React presentation layer: components keep pure props, attachment data, upload state, image loading, and callbacks all come from the slot owners, and strings resolve through the owning plugin's locale namespace; `ui-conversation` and (for tool-result galleries) `ui-tool` are its current consumers. It waits through `ctx.slots.inject` for `conversation.input.attachments`, `conversation.message.images`, `conversation.trajectory.images`, and `tool.call.images`.

- `AttachmentRail`: images and generic files enter one non-wrapping draft rail in selection order, every entry 64px high — images are 64px squares, files are 240px-wide DeepSeek Web cards (16px radius, document icon, filename, uppercase extension, byte size). Overflow is paged with edge arrows while the scrollbar stays hidden; a file upload shows a spinner/progress (indeterminate before the first byte report) and a retry on failure, the remove control appears on hover or keyboard focus and stays visible on touch (`prefers-reduced-motion: reduce` gives instant scrolling)

- `MessageImage` / `ImageGallery`: Chat places files and images in one right-aligned, wrapping arrangement that preserves source order; a single image with no other attachment renders at a 240px longest side, while multiple attachments render each image as a 64px square beside 240×64px file cards. Load failure offers an explicit retry; clicking opens `ImageLightbox`

- `ImageLightbox`: document-level modal preview, closed by Escape / background click / close control, focus returned to the opener on unmount

**Model visibility**: none — it renders a pure React atom in the browser and never enters any model request.

## 5. Configuration

`attachment-local`'s admission limits and normalization policy are all configurable (0.1.1, defaults below); the storage root is still resolved from `DSH_HOME`. The mount line, as in the default composition:

| Option | Default | Meaning |
| --- | --- | --- |
| maxImageBytes | 20 MiB | per-image byte cap |
| maxImagesPerMessage | 20 | image-count cap per message |
| maxMessageImageBytes | 200 MiB | total image-byte cap per message |
| maxImagePixels | 64 M | per-image pixel cap |
| maxImageDimension | 8192 | per-side dimension cap |
| normalizedImageMaxDimension | 2048 | per-side cap after normalization re-encode |
| normalizedImageMaxBytes | 4 MiB | byte cap after normalization re-encode |
| imageCompressionConcurrency | 2 (max 8) | compression/normalization concurrency |

```yaml
- id: attachment-local

  name: '@deepseek-ai/dsh-attachment-local'
```

Before commit, every image is **deterministically re-encoded** under the normalization policy (shrunk to the normalized caps when over them); what lands on disk is the normalized encoding. `saveImage`/`saveImages` return the canonical ref beside the source facts and normalization facts. These limits apply to images only: the generic file write path imposes no type or size limit. `readImageRequest` (0.1.1) is the combined "read + project the request payload per the model route's policy" API, with request-level deduplication.

## 6. Known limitations

- Raster image limits apply to images only: images accept PNG, JPEG, WebP, and GIF within deployment limits, while any other file is stored verbatim with no type or size limit; audio and video have no dedicated handling yet

- Retention and garbage collection are deferred (recovered/derived sessions may share immutable objects)

- Persisting unsent drafts, audio, and video need their own lifecycle and provider contracts

## 7. Verification

```sh
# Check whether attachment-local is mounted

dsh web --dump-config | grep -iE "attachment"

# Look at the attachment object directory (owner-only, bucketed by sha256 prefix)

ls -la ~/.dsh/attachments/v1/objects/

# Generic files: canonical objects and read-only reference paths

ls -la ~/.dsh/attachments/v1/file-objects/ ~/.dsh/attachments/v1/files/
```

## Next steps

- [Storage](../features/storage.md): another kind of non-session persistent data (KV backends); attachments do not go through here

- [Session system](../learn/core/session.md): session logs only store `sha256:` references and validated metadata

- [Built-in tools](../features/tools.md): images enter provider requests as `ImageBlock`, while generic files project only a handle line
