window.__ModuleLoader__.load({
	id: "@rabbit-dsh/sidebar-template",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		let _deepseek_ai_dsh_client_ui_primitives = require("@deepseek-ai/dsh-client-ui-primitives");
		let _deepseek_ai_dsh_client_ui_slots = require("@deepseek-ai/dsh-client-ui-slots");
		let react = require("react");
		let react_jsx_runtime = require("react/jsx-runtime");
		// \0sidebar-template-css:/Users/whit3rabbit/Documents/GitHub/skill-auditor/skills/rabbit-dsh/examples/sidebar/src/client/ui-kit.module.css.mjs
		const css = ".coyB9a_tabRoot{background:var(--dsw-alias-bg-layer-1);height:100%;min-height:0;color:var(--dsw-alias-label-primary);font:var(--dsw-font-xxs-12);flex-direction:column;display:flex}.coyB9a_tabBodyScroll{flex-direction:column;flex:1;gap:8px;min-height:0;padding:10px 12px;display:flex;overflow:auto}.coyB9a_iconBtn{width:28px;height:28px;color:var(--dsw-alias-label-secondary);cursor:pointer;background:0 0;border:1px solid #0000;border-radius:6px;flex-shrink:0;justify-content:center;align-items:center;padding:0;transition:background-color .12s,color .12s,border-color .12s;display:inline-flex}.coyB9a_iconBtnSm{border-radius:4px;width:24px;height:24px}.coyB9a_iconBtn:hover:not(:disabled){background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}.coyB9a_iconBtn:focus-visible{border-color:var(--dsw-alias-border-l4);outline:none}.coyB9a_iconBtnActive{background:var(--dsw-alias-accent-soft);color:var(--dsw-alias-button-primary-fill)}.coyB9a_iconBtnDanger:hover:not(:disabled){background:color-mix(in srgb, var(--dsw-alias-state-error-primary) 12%, transparent);color:var(--dsw-alias-state-error-primary)}.coyB9a_iconBtn:disabled{opacity:.4;cursor:not-allowed}.coyB9a_chip{border:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-2);height:22px;color:var(--dsw-alias-label-secondary);font:var(--dsw-font-xxxs-11);cursor:pointer;user-select:none;white-space:nowrap;border-radius:999px;align-items:center;gap:4px;padding:0 8px;transition:background-color .12s,color .12s,border-color .12s;display:inline-flex}.coyB9a_chip:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}.coyB9a_chipActive{background:var(--dsw-alias-accent-soft);border-color:color-mix(in srgb, var(--dsw-alias-button-primary-fill) 32%, transparent);color:var(--dsw-alias-button-primary-fill);font-weight:500}.coyB9a_chipCount{background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-tertiary);font-variant-numeric:tabular-nums;border-radius:999px;padding:0 4px}.coyB9a_sectionHeader{border-bottom:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);flex-shrink:0;justify-content:space-between;align-items:center;gap:8px;height:28px;padding:0 10px;display:flex}.coyB9a_sectionHeaderLeft{align-items:center;gap:6px;min-width:0;display:inline-flex}.coyB9a_sectionHeaderLabel{color:var(--dsw-alias-label-secondary);font:var(--dsw-font-xxxs-11);text-transform:uppercase;letter-spacing:.04em;font-weight:600}.coyB9a_sectionHeaderCount{background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-tertiary);font:var(--dsw-font-xxxs-11);font-variant-numeric:tabular-nums;border-radius:999px;padding:0 5px}.coyB9a_sectionHeaderRight{align-items:center;gap:2px;display:inline-flex}.coyB9a_notice{color:var(--dsw-alias-label-secondary);font:var(--dsw-font-xxs-12);border-radius:8px;flex-direction:column;gap:6px;padding:12px;display:flex}.coyB9a_noticePage{text-align:center;align-items:center;max-width:280px;margin:auto;padding:24px 16px}.coyB9a_noticeWell{background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l1)}.coyB9a_noticeInline{background:var(--dsw-alias-bg-layer-2);border-radius:6px;padding:6px 8px}.coyB9a_noticeError{border-color:color-mix(in srgb, var(--dsw-alias-state-error-primary) 35%, transparent);color:var(--dsw-alias-state-error-primary)}.coyB9a_noticeWarn{border-color:color-mix(in srgb, var(--dsw-alias-state-warn-primary) 35%, transparent);color:var(--dsw-alias-state-warn-primary)}.coyB9a_noticeTitle{color:var(--dsw-alias-label-primary);font-weight:600}.coyB9a_noticeDetail{color:var(--dsw-alias-label-tertiary);font:var(--dsw-font-xxxs-11)}.coyB9a_noticeSpinner{border:2px solid var(--dsw-alias-border-l2);border-top-color:var(--dsw-alias-button-primary-fill);border-radius:50%;width:16px;height:16px;animation:.75s linear infinite coyB9a_dshUiSpin}@keyframes coyB9a_dshUiSpin{to{transform:rotate(360deg)}}.coyB9a_statusBadge{height:18px;font:var(--dsw-font-xxxs-11);background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-secondary);border-radius:4px;align-items:center;gap:4px;padding:0 6px;font-weight:500;display:inline-flex}.coyB9a_statusBadge[data-tone=info]{background:color-mix(in srgb, var(--dsw-alias-state-business-primary) 14%, transparent);color:var(--dsw-alias-state-business-primary)}.coyB9a_statusBadge[data-tone=success]{background:color-mix(in srgb, var(--dsw-alias-state-success-primary) 14%, transparent);color:var(--dsw-alias-state-success-primary)}.coyB9a_statusBadge[data-tone=warn]{background:color-mix(in srgb, var(--dsw-alias-state-warn-primary) 14%, transparent);color:var(--dsw-alias-state-warn-primary)}.coyB9a_statusBadge[data-tone=error]{background:color-mix(in srgb, var(--dsw-alias-state-error-primary) 14%, transparent);color:var(--dsw-alias-state-error-primary)}.coyB9a_switchRoot{cursor:pointer;flex-shrink:0;align-items:center;display:inline-flex;position:relative}.coyB9a_switchInput{opacity:0;width:0;height:0;position:absolute}.coyB9a_switchTrack{background:var(--dsw-alias-bg-layer-2);border:1px solid var(--dsw-alias-border-l2);border-radius:999px;align-items:center;width:34px;height:20px;padding:2px;transition:background-color .14s,border-color .14s;display:inline-flex}.coyB9a_switchThumb{background:var(--dsw-alias-label-secondary);border-radius:50%;width:14px;height:14px;transition:transform .14s,background-color .14s}.coyB9a_switchInput:checked+.coyB9a_switchTrack{background:var(--dsw-alias-button-primary-fill);border-color:var(--dsw-alias-button-primary-fill)}.coyB9a_switchInput:checked+.coyB9a_switchTrack .coyB9a_switchThumb{background:var(--dsw-alias-bg-base);transform:translate(14px)}.coyB9a_switchInput:focus-visible+.coyB9a_switchTrack{outline:2px solid var(--dsw-alias-border-l4);outline-offset:1px}.coyB9a_settingsPage{flex-direction:column;gap:20px;display:flex}.coyB9a_groupTitle{color:var(--dsw-alias-label-secondary);font:var(--dsw-font-xxs-12);margin:0 0 8px;font-weight:600}.coyB9a_groupCard{background:var(--dsw-alias-bg-layer-3);border:1px solid var(--dsw-alias-border-l1);border-radius:16px;overflow:hidden}.coyB9a_settingRow{justify-content:space-between;align-items:center;gap:16px;padding:12px 16px;display:flex}.coyB9a_settingRow+.coyB9a_settingRow{border-top:1px solid var(--dsw-alias-border-l1)}.coyB9a_settingCopy{flex-direction:column;gap:2px;min-width:0;display:flex}.coyB9a_settingLabel{color:var(--dsw-alias-label-primary);font:var(--dsw-font-xs-13,var(--dsw-font-xxs-12));font-weight:500}.coyB9a_settingDesc{color:var(--dsw-alias-label-tertiary);font:var(--dsw-font-xxxs-11)}.coyB9a_featureGrid{grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;display:grid}.coyB9a_featureCard{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-2);border-radius:12px;flex-direction:column;justify-content:space-between;transition:border-color .12s,background-color .12s;display:flex;overflow:hidden}.coyB9a_featureCardActive{border-color:color-mix(in srgb, var(--dsw-alias-button-primary-fill) 45%, var(--dsw-alias-border-l2));background:color-mix(in srgb, var(--dsw-alias-accent-soft) 35%, var(--dsw-alias-bg-layer-2))}.coyB9a_featureCardTop{justify-content:space-between;align-items:flex-start;gap:8px;padding:12px;display:flex}.coyB9a_featureCardTitle{color:var(--dsw-alias-label-primary);font:var(--dsw-font-xxs-12);font-weight:600}.coyB9a_featureCardDesc{color:var(--dsw-alias-label-tertiary);font:var(--dsw-font-xxxs-11);margin-top:4px}.coyB9a_featureCardFooter{border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-layer-1);justify-content:space-between;align-items:center;padding:6px 12px;display:flex}";
		const tagId = "@rabbit-dsh/sidebar-template/ui-kit.module.css";
		if (typeof document !== "undefined" && document.querySelector("style[data-plugin-css=" + JSON.stringify(tagId) + "]") === null) {
			const tag = document.createElement("style");
			tag.dataset.plugin = "@rabbit-dsh/sidebar-template";
			tag.dataset.pluginCss = tagId;
			tag.textContent = css;
			document.head.appendChild(tag);
		}
		var ui_kit_module_css_default = {
			"featureCardTitle": "coyB9a_featureCardTitle",
			"settingCopy": "coyB9a_settingCopy",
			"iconBtnActive": "coyB9a_iconBtnActive",
			"iconBtn": "coyB9a_iconBtn",
			"noticePage": "coyB9a_noticePage",
			"switchThumb": "coyB9a_switchThumb",
			"switchRoot": "coyB9a_switchRoot",
			"sectionHeaderLabel": "coyB9a_sectionHeaderLabel",
			"featureCardFooter": "coyB9a_featureCardFooter",
			"settingDesc": "coyB9a_settingDesc",
			"chip": "coyB9a_chip",
			"iconBtnDanger": "coyB9a_iconBtnDanger",
			"noticeSpinner": "coyB9a_noticeSpinner",
			"tabRoot": "coyB9a_tabRoot",
			"dshUiSpin": "coyB9a_dshUiSpin",
			"sectionHeaderLeft": "coyB9a_sectionHeaderLeft",
			"noticeDetail": "coyB9a_noticeDetail",
			"featureCardDesc": "coyB9a_featureCardDesc",
			"featureCard": "coyB9a_featureCard",
			"featureCardActive": "coyB9a_featureCardActive",
			"noticeError": "coyB9a_noticeError",
			"groupTitle": "coyB9a_groupTitle",
			"settingLabel": "coyB9a_settingLabel",
			"switchTrack": "coyB9a_switchTrack",
			"chipCount": "coyB9a_chipCount",
			"iconBtnSm": "coyB9a_iconBtnSm",
			"noticeWarn": "coyB9a_noticeWarn",
			"sectionHeader": "coyB9a_sectionHeader",
			"settingsPage": "coyB9a_settingsPage",
			"sectionHeaderRight": "coyB9a_sectionHeaderRight",
			"noticeTitle": "coyB9a_noticeTitle",
			"settingRow": "coyB9a_settingRow",
			"featureGrid": "coyB9a_featureGrid",
			"chipActive": "coyB9a_chipActive",
			"noticeWell": "coyB9a_noticeWell",
			"notice": "coyB9a_notice",
			"statusBadge": "coyB9a_statusBadge",
			"switchInput": "coyB9a_switchInput",
			"tabBodyScroll": "coyB9a_tabBodyScroll",
			"noticeInline": "coyB9a_noticeInline",
			"sectionHeaderCount": "coyB9a_sectionHeaderCount",
			"groupCard": "coyB9a_groupCard",
			"featureCardTop": "coyB9a_featureCardTop"
		};
		// src/client/ui-kit.tsx
		function IconButton({ size = "md", active = false, danger = false, className, children, ...rest }) {
			const cls = [
				ui_kit_module_css_default.iconBtn,
				size === "sm" ? ui_kit_module_css_default.iconBtnSm : "",
				active ? ui_kit_module_css_default.iconBtnActive : "",
				danger ? ui_kit_module_css_default.iconBtnDanger : "",
				className ?? ""
			].filter(Boolean).join(" ");
			return /* @__PURE__ */ (0, react_jsx_runtime.jsx)("button", {
				type: "button",
				className: cls,
				...rest,
				children
			});
		}
		function Chip({ active = false, count, onClick, children }) {
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("button", {
				type: "button",
				className: `${ui_kit_module_css_default.chip} ${active ? ui_kit_module_css_default.chipActive : ""}`,
				onClick,
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", { children }), typeof count === "number" && /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
					className: ui_kit_module_css_default.chipCount,
					children: count
				})]
			});
		}
		function SectionHeader({ label, count, action }) {
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				className: ui_kit_module_css_default.sectionHeader,
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
					className: ui_kit_module_css_default.sectionHeaderLeft,
					children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
						className: ui_kit_module_css_default.sectionHeaderLabel,
						children: label
					}), typeof count === "number" && /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
						className: ui_kit_module_css_default.sectionHeaderCount,
						children: count
					})]
				}), action && /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
					className: ui_kit_module_css_default.sectionHeaderRight,
					children: action
				})]
			});
		}
		function Notice({ kind = "empty", tone = "well", title, detail, action }) {
			const cls = [
				ui_kit_module_css_default.notice,
				tone === "page" ? ui_kit_module_css_default.noticePage : tone === "inline" ? ui_kit_module_css_default.noticeInline : ui_kit_module_css_default.noticeWell,
				kind === "error" ? ui_kit_module_css_default.noticeError : kind === "warn" ? ui_kit_module_css_default.noticeWarn : ""
			].filter(Boolean).join(" ");
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				className: cls,
				role: kind === "error" ? "alert" : "status",
				children: [
					kind === "loading" && /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
						className: ui_kit_module_css_default.noticeSpinner,
						"aria-hidden": "true"
					}),
					title && /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						className: ui_kit_module_css_default.noticeTitle,
						children: title
					}),
					detail && /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						className: ui_kit_module_css_default.noticeDetail,
						children: detail
					}),
					action && /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", { children: action })
				]
			});
		}
		function StatusBadge({ tone = "neutral", children }) {
			return /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
				className: ui_kit_module_css_default.statusBadge,
				"data-tone": tone,
				children
			});
		}
		function Switch({ checked, onChange, disabled = false, ariaLabel }) {
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("label", {
				className: ui_kit_module_css_default.switchRoot,
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("input", {
					type: "checkbox",
					className: ui_kit_module_css_default.switchInput,
					checked,
					disabled,
					"aria-label": ariaLabel,
					onChange: (e) => onChange(e.target.checked)
				}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
					className: ui_kit_module_css_default.switchTrack,
					children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", { className: ui_kit_module_css_default.switchThumb })
				})]
			});
		}
		function ConfirmDialog({ open, title, description, confirmLabel = "Confirm", cancelLabel = "Cancel", onConfirm, onClose }) {
			if (!open) return null;
			return /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Modal, {
				open,
				onClose,
				title,
				description,
				closeLabel: cancelLabel,
				footer: /* @__PURE__ */ (0, react_jsx_runtime.jsxs)(react_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Button, {
					variant: "outline",
					onClick: onClose,
					children: cancelLabel
				}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Button, {
					variant: "primary",
					onClick: () => {
						onConfirm();
						onClose();
					},
					children: confirmLabel
				})] })
			});
		}
		function SelectMenu({ value, items, onSelect }) {
			const [open, setOpen] = (0, react.useState)(false);
			const triggerRef = (0, react.useRef)(null);
			const current = items.find((item) => item.id === value);
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)(react_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)(_deepseek_ai_dsh_client_ui_primitives.Button, {
				ref: triggerRef,
				variant: "outline",
				onClick: () => setOpen((prev) => !prev),
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", { children: current?.label ?? value }), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconChevronDownOutlineRegular, { size: 14 })]
			}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Menu, {
				open,
				anchor: triggerRef.current,
				items,
				selectedId: value,
				onSelect: (id) => {
					onSelect(id);
					setOpen(false);
				},
				onClose: () => setOpen(false),
				portal: true
			})] });
		}
		function FeatureCard({ title, description, enabled, onToggle, onOpenSettings }) {
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				className: `${ui_kit_module_css_default.featureCard} ${enabled ? ui_kit_module_css_default.featureCardActive : ""}`,
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
					className: ui_kit_module_css_default.featureCardTop,
					children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						className: ui_kit_module_css_default.featureCardTitle,
						children: title
					}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
						className: ui_kit_module_css_default.featureCardDesc,
						children: description
					})] }), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(Switch, {
						checked: enabled,
						onChange: onToggle,
						ariaLabel: `Toggle ${title}`
					})]
				}), onOpenSettings && /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
					className: ui_kit_module_css_default.featureCardFooter,
					children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)(StatusBadge, {
						tone: enabled ? "success" : "neutral",
						children: enabled ? "Enabled" : "Disabled"
					}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(IconButton, {
						size: "sm",
						"aria-label": `Configure ${title}`,
						onClick: onOpenSettings,
						children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconSettingsOutlineRegular, { size: 14 })
					})]
				})]
			});
		}
		// src/client/index.tsx
		const name = "sidebar-template-client";
		/**
		* Declare required services in `inject` (module level — the Loader wires them
		* before `apply` runs). If your plugin only targets `dsh-better-sidebar`, use
		* `export const inject = ['betterSidebar']`. Here we declare the stock web
		* seats and read `betterSidebar` (the optional extension) with `ctx.get`,
		* so the template works in both setups.
		*/
		const inject = [
			"slots",
			"sidebarRight",
			"sidebarRightTabs"
		];
		const BETTER_SIDEBAR_TAB_ID = "sidebar-template:inspector";
		const NATIVE_TAB_KEY = "sidebar-template:inspector";
		const NATIVE_TAB_KIND = "sidebar-template-inspector";
		const SETTINGS_SECTION_ID = "sidebar-template-settings";
		function InspectorPanel({ sessionId, visible, betterSidebar }) {
			const [mode, setMode] = (0, react.useState)("events");
			const [filter, setFilter] = (0, react.useState)("all");
			const [confirmResetOpen, setConfirmResetOpen] = (0, react.useState)(false);
			const [tick, setTick] = (0, react.useState)(0);
			(0, react.useEffect)(() => {
				if (!visible) return;
				const timer = window.setInterval(() => {
					setTick((prev) => prev + 1);
				}, 1e4);
				return () => window.clearInterval(timer);
			}, [visible]);
			const prefsUrl = betterSidebar ? betterSidebar.hostRouteUrl("sidebar-template/api/prefs") : "sidebar-template/api/prefs";
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				className: ui_kit_module_css_default.tabRoot,
				children: [
					/* @__PURE__ */ (0, react_jsx_runtime.jsx)(SectionHeader, {
						label: "Session Inspector",
						count: 3,
						action: /* @__PURE__ */ (0, react_jsx_runtime.jsxs)(react_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Tooltip, {
							content: `Refresh (${prefsUrl})`,
							children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(IconButton, {
								size: "sm",
								"aria-label": "Refresh inspector",
								onClick: () => setTick((prev) => prev + 1),
								children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconRefreshOutlineRegular, { size: 14 })
							})
						}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Tooltip, {
							content: "Reset state",
							children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(IconButton, {
								size: "sm",
								danger: true,
								"aria-label": "Reset inspector state",
								onClick: () => setConfirmResetOpen(true),
								children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconSettingsOutlineRegular, { size: 14 })
							})
						})] })
					}),
					/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
						className: ui_kit_module_css_default.tabBodyScroll,
						children: [
							/* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.SegmentedControl, {
								ariaLabel: "Inspector view mode",
								value: mode,
								onChange: (next) => setMode(next),
								options: [{
									value: "events",
									label: "Events"
								}, {
									value: "metrics",
									label: "Metrics"
								}]
							}),
							/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
								style: {
									display: "flex",
									gap: 6,
									flexWrap: "wrap"
								},
								children: [
									/* @__PURE__ */ (0, react_jsx_runtime.jsx)(Chip, {
										active: filter === "all",
										count: 3,
										onClick: () => setFilter("all"),
										children: "All"
									}),
									/* @__PURE__ */ (0, react_jsx_runtime.jsx)(Chip, {
										active: filter === "warn",
										count: 1,
										onClick: () => setFilter("warn"),
										children: "Warnings"
									}),
									/* @__PURE__ */ (0, react_jsx_runtime.jsx)(Chip, {
										active: filter === "error",
										count: 0,
										onClick: () => setFilter("error"),
										children: "Errors"
									})
								]
							}),
							mode === "events" ? /* @__PURE__ */ (0, react_jsx_runtime.jsx)(Notice, {
								kind: "hint",
								tone: "well",
								title: /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("span", {
									style: {
										display: "inline-flex",
										alignItems: "center",
										gap: 6
									},
									children: [
										/* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.StateDot, { state: "success" }),
										/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("span", { children: [
											"Session ",
											sessionId || "global",
											" active"
										] }),
										/* @__PURE__ */ (0, react_jsx_runtime.jsxs)(StatusBadge, {
											tone: "info",
											children: ["poll #", tick]
										})
									]
								}),
								detail: "Replace this block with your domain tree, live trace stream, or resource cards."
							}) : /* @__PURE__ */ (0, react_jsx_runtime.jsx)(Notice, {
								kind: "empty",
								tone: "page",
								title: "No metrics recorded yet",
								detail: "Trigger a tool call in the active session to populate metrics."
							})
						]
					}),
					/* @__PURE__ */ (0, react_jsx_runtime.jsx)(ConfirmDialog, {
						open: confirmResetOpen,
						title: "Reset Inspector State?",
						description: "This clears local inspector counters for the active session.",
						confirmLabel: "Reset",
						onConfirm: () => setTick(0),
						onClose: () => setConfirmResetOpen(false)
					})
				]
			});
		}
		function TraceLogViewer({ path, content }) {
			const lines = (content ?? "").split("\n").filter(Boolean);
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				className: ui_kit_module_css_default.tabRoot,
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)(SectionHeader, {
					label: path,
					count: lines.length
				}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
					className: ui_kit_module_css_default.tabBodyScroll,
					children: lines.length === 0 ? /* @__PURE__ */ (0, react_jsx_runtime.jsx)(Notice, {
						kind: "empty",
						tone: "page",
						title: "Empty trace log"
					}) : lines.map((line, idx) => /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
						className: ui_kit_module_css_default.noticeInline,
						children: [
							/* @__PURE__ */ (0, react_jsx_runtime.jsxs)(StatusBadge, {
								tone: line.includes("ERROR") ? "error" : "info",
								children: ["#", idx + 1]
							}),
							" ",
							/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", { children: line })
						]
					}, idx))
				})]
			});
		}
		function SidebarTemplateSettingsPage() {
			const [inspectorEnabled, setInspectorEnabled] = (0, react.useState)(true);
			const [headerToggleEnabled, setHeaderToggleEnabled] = (0, react.useState)(true);
			const [defaultDock, setDefaultDock] = (0, react.useState)("right");
			const [pollSeconds, setPollSeconds] = (0, react.useState)("10");
			return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
				className: ui_kit_module_css_default.settingsPage,
				children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("section", { children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("h3", {
					className: ui_kit_module_css_default.groupTitle,
					children: "Sidebar Features"
				}), /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
					className: ui_kit_module_css_default.featureGrid,
					children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)(FeatureCard, {
						title: "Session Inspector",
						description: "Live event and metric inspector in the right sidebar or bottom dock.",
						enabled: inspectorEnabled,
						onToggle: setInspectorEnabled,
						onOpenSettings: () => {}
					}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(FeatureCard, {
						title: "Header Quick Toggle",
						description: "Pin a one-click utility button in the conversation session header.",
						enabled: headerToggleEnabled,
						onToggle: setHeaderToggleEnabled
					})]
				})] }), /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("section", { children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("h3", {
					className: ui_kit_module_css_default.groupTitle,
					children: "Behavior & Defaults"
				}), /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
					className: ui_kit_module_css_default.groupCard,
					children: [
						/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
							className: ui_kit_module_css_default.settingRow,
							children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
								className: ui_kit_module_css_default.settingCopy,
								children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
									className: ui_kit_module_css_default.settingLabel,
									children: "Default Dock Target"
								}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
									className: ui_kit_module_css_default.settingDesc,
									children: "Choose whether new Inspector tabs open in the right sidebar or bottom workbench."
								})]
							}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(SelectMenu, {
								value: defaultDock,
								onSelect: setDefaultDock,
								items: [{
									id: "right",
									label: "Right Sidebar"
								}, {
									id: "bottom",
									label: "Bottom Workbench"
								}]
							})]
						}),
						/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
							className: ui_kit_module_css_default.settingRow,
							children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
								className: ui_kit_module_css_default.settingCopy,
								children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
									className: ui_kit_module_css_default.settingLabel,
									children: "Refresh Interval (seconds)"
								}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
									className: ui_kit_module_css_default.settingDesc,
									children: "Background polling interval while the tab is visible in the active pane."
								})]
							}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("div", {
								style: { width: 96 },
								children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Input, {
									type: "number",
									value: pollSeconds,
									onChange: (e) => setPollSeconds(e.target.value)
								})
							})]
						}),
						/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
							className: ui_kit_module_css_default.settingRow,
							children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
								className: ui_kit_module_css_default.settingCopy,
								children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
									className: ui_kit_module_css_default.settingLabel,
									children: "Auto-reveal on Warnings"
								}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", {
									className: ui_kit_module_css_default.settingDesc,
									children: "Automatically focus the Inspector tab when a tool emits a warning."
								})]
							}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(Switch, {
								checked: inspectorEnabled,
								onChange: setInspectorEnabled,
								ariaLabel: "Toggle auto-reveal on warnings"
							})]
						})
					]
				})] })]
			});
		}
		function apply(ctx) {
			const betterSidebar = ctx.get("betterSidebar");
			if (betterSidebar) ctx.effect(() => {
				const disposeTab = betterSidebar.registerTab({
					id: BETTER_SIDEBAR_TAB_ID,
					title: "Inspector",
					description: "Inspect session events, tool calls, and live metrics.",
					icon: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconCodeOutlineRegular, { size: 16 }),
					order: 60,
					single: true,
					bottomOnly: false,
					settings: {
						pluginToggles: [
							{
								key: "autoReveal",
								title: "Auto-reveal on warnings",
								desc: "Open the Inspector tab when a tool call reports a warning.",
								type: "switch"
							},
							{
								key: "refreshIntervalSec",
								title: "Refresh interval",
								desc: "Polling interval while the tab is visible.",
								type: "number",
								min: 1,
								max: 300,
								unit: "s"
							},
							{
								key: "defaultFilter",
								title: "Default event filter",
								desc: "Initial filter chip selected when the tab mounts.",
								type: "select",
								options: [
									{
										value: "all",
										title: "All events"
									},
									{
										value: "warn",
										title: "Warnings only"
									},
									{
										value: "error",
										title: "Errors only"
									}
								]
							},
							{
								key: "ignoredGlobs",
								title: "Ignored paths",
								desc: "One glob pattern per line.",
								type: "patterns",
								patternsPlaceholder: "node_modules\n.git"
							}
						],
						render: ({ pluginSettings, updatePluginSetting, close }) => /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("div", {
							style: {
								display: "flex",
								justifyContent: "space-between",
								paddingTop: 8
							},
							children: [/* @__PURE__ */ (0, react_jsx_runtime.jsxs)(StatusBadge, {
								tone: "info",
								children: ["Filter: ", String(pluginSettings.defaultFilter ?? "all")]
							}), /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Button, {
								variant: "outline",
								onClick: () => {
									updatePluginSetting("defaultFilter", "all");
									close();
								},
								children: "Reset & Close"
							})]
						})
					},
					component: ({ scope, visible }) => /* @__PURE__ */ (0, react_jsx_runtime.jsx)(InspectorPanel, {
						sessionId: scope,
						visible,
						betterSidebar
					})
				});
				const disposeViewer = betterSidebar.registerFileViewer({
					id: "sidebar-template:trace-viewer",
					title: "Trace Log",
					icon: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconCodeOutlineRegular, { size: 14 }),
					exts: ["log", "trace"],
					priority: 10,
					fetchStrategy: "fsRead",
					component: TraceLogViewer
				});
				return () => {
					disposeTab();
					disposeViewer();
				};
			}, "sidebar-template: better-sidebar tab + viewer");
			ctx.effect(() => ctx.sidebarRightTabs.register({
				id: NATIVE_TAB_KEY,
				kind: NATIVE_TAB_KIND,
				keepMounted: true,
				priority: "extension",
				title: () => "Inspector",
				guide: [{
					id: NATIVE_TAB_KIND,
					order: 60,
					title: () => "Inspector",
					description: () => "Inspect live session events and metrics.",
					icon: ({ size = 16 }) => /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconCodeOutlineRegular, { size })
				}]
			}));
			ctx.slots.inject("sidebar.right.pane.tab", () => ctx.slots.register({
				name: "sidebar.right.pane.tab",
				key: NATIVE_TAB_KEY,
				inject: (sessionId) => ({ sessionId })
			}, function NativeInspectorTabBody(props) {
				const { sessionId } = (0, _deepseek_ai_dsh_client_ui_slots.useInjected)();
				return /* @__PURE__ */ (0, react_jsx_runtime.jsx)(InspectorPanel, {
					sessionId: sessionId || props.sessionId,
					visible: true
				});
			}));
			ctx.slots.inject("sidebar.right.pane.tab.title", () => ctx.slots.register({
				name: "sidebar.right.pane.tab.title",
				key: NATIVE_TAB_KEY
			}, function NativeInspectorTabTitle(_props) {
				return /* @__PURE__ */ (0, react_jsx_runtime.jsxs)("span", {
					style: {
						display: "inline-flex",
						alignItems: "center",
						gap: 6
					},
					children: [/* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconCodeOutlineRegular, { size: 14 }), /* @__PURE__ */ (0, react_jsx_runtime.jsx)("span", { children: "Inspector" })]
				});
			}));
			ctx.slots.inject("conversation.session.header.utilities", () => ctx.slots.register({
				name: "conversation.session.header.utilities",
				id: "sidebar-template-header-toggle",
				order: 50
			}, function HeaderInspectorToggle() {
				return /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.Tooltip, {
					content: "Open Session Inspector",
					children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(IconButton, {
						size: "sm",
						"aria-label": "Open Session Inspector",
						onClick: () => {
							const extension = ctx.get("betterSidebar");
							if (extension) extension.openTab({
								type: BETTER_SIDEBAR_TAB_ID,
								target: "right",
								reveal: true
							});
							else ctx.sidebarRight.openTab(NATIVE_TAB_KIND, { revealIfOpened: true });
						},
						children: /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconPanelLeftOutlineRegular, { size: 14 })
					})
				});
			}));
			ctx.slots.inject("settings.section.icon", () => ctx.slots.register({
				name: "settings.section.icon",
				id: SETTINGS_SECTION_ID,
				order: 85,
				label: () => "Sidebar Template"
			}, ({ size }) => /* @__PURE__ */ (0, react_jsx_runtime.jsx)(_deepseek_ai_dsh_client_ui_primitives.IconPanelLeftOutlineRegular, { size })));
			ctx.slots.inject("settings.section", () => ctx.slots.register({
				name: "settings.section",
				id: SETTINGS_SECTION_ID,
				order: 85,
				label: () => "Sidebar Template"
			}, SidebarTemplateSettingsPage));
		}
		exports.apply = apply;
		exports.inject = inject;
		exports.name = name;
		return module.exports;
	}
});

//# sourceMappingURL=client.js.map