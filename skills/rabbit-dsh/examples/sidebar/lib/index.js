import z from "@deepseek-ai/schemastery";
// src/index.ts
const name = "sidebar-template";
const inject = [
	"webServer",
	"connection",
	"settings",
	"loader"
];
const Config = z.object({
	enableInspectorTab: z.boolean().default(true).description("Enable the Inspector tab in the right sidebar or bottom dock.").volatile(),
	enableBottomDockToggle: z.boolean().default(true).description("Show the quick-toggle button in the session header utility bar.").volatile(),
	refreshIntervalSec: z.number().min(1).max(300).default(10).description("Polling interval in seconds while the sidebar tab is visible.").volatile(),
	ignoredGlobs: z.string().default("node_modules\n.git").description("Newline-separated ignore patterns for the sidebar inspector.").volatile()
});
const DEFAULT_PREFS = {
	enableInspectorTab: true,
	enableBottomDockToggle: true,
	refreshIntervalSec: 10,
	ignoredGlobs: "node_modules\n.git"
};
/**
* The settings namespace of this plugin is its profile patch-row id
* (`id: sidebar-template` in cordis.patch.yml). `ctx.settings.describe()`
* keys live plugin forms by that same id, and `ctx.settings.update(ns, patch)`
* merges user edits into the profile's user layer.
*/
const SETTINGS_NS = "sidebar-template";
function readPrefs(ctx, config) {
	const raw = (ctx.settings?.describe().find((row) => row.ns === SETTINGS_NS))?.value ?? {};
	return {
		enableInspectorTab: typeof raw.enableInspectorTab === "boolean" ? raw.enableInspectorTab : config.enableInspectorTab?.value ?? DEFAULT_PREFS.enableInspectorTab,
		enableBottomDockToggle: typeof raw.enableBottomDockToggle === "boolean" ? raw.enableBottomDockToggle : config.enableBottomDockToggle?.value ?? DEFAULT_PREFS.enableBottomDockToggle,
		refreshIntervalSec: typeof raw.refreshIntervalSec === "number" ? raw.refreshIntervalSec : config.refreshIntervalSec?.value ?? DEFAULT_PREFS.refreshIntervalSec,
		ignoredGlobs: typeof raw.ignoredGlobs === "string" ? raw.ignoredGlobs : config.ignoredGlobs?.value ?? DEFAULT_PREFS.ignoredGlobs
	};
}
async function writePrefs(ctx, current, patch) {
	const next = {
		...current,
		...patch
	};
	if (ctx.settings) await ctx.settings.update(SETTINGS_NS, next);
	return next;
}
function guardAdmission(ctx, req, res) {
	const rejection = ctx.connection.requestRejection(req);
	if (!rejection) return true;
	res.writeHead(rejection.statusCode, { "content-type": "application/json; charset=utf-8" });
	res.end(JSON.stringify({
		ok: false,
		error: rejection.message
	}));
	return false;
}
function apply(ctx, config) {
	const webServer = ctx.webServer;
	ctx.effect(() => {
		ctx.settings?.configure({ auto: false }, ctx.fiber);
		return () => {};
	});
	ctx.effect(() => webServer.register({
		kind: "exact",
		path: "/sidebar-template/api/prefs",
		handler: async (req, res) => {
			if (!guardAdmission(ctx, req, res)) return;
			const method = (req.method || "GET").toUpperCase();
			if (method === "GET") {
				res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
				res.end(JSON.stringify({
					ok: true,
					prefs: readPrefs(ctx, config)
				}));
				return;
			}
			if (method !== "POST") {
				res.writeHead(405, { "content-type": "application/json; charset=utf-8" });
				res.end(JSON.stringify({
					ok: false,
					error: "method not allowed"
				}));
				return;
			}
			const chunks = [];
			req.on("data", (chunk) => chunks.push(chunk));
			await new Promise((resolve) => req.on("end", resolve));
			try {
				const patch = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
				const prefs = await writePrefs(ctx, readPrefs(ctx, config), patch);
				res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
				res.end(JSON.stringify({
					ok: true,
					prefs
				}));
			} catch (err) {
				res.writeHead(400, { "content-type": "application/json; charset=utf-8" });
				res.end(JSON.stringify({
					ok: false,
					error: err.message
				}));
			}
		}
	}));
}
export { Config, apply, inject, name };
