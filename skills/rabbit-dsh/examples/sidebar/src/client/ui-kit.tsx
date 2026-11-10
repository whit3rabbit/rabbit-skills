import {
  Button,
  IconChevronDownOutlineRegular,
  IconSettingsOutlineRegular,
  Menu,
  type MenuItem,
  Modal,
} from '@deepseek-ai/dsh-client-ui-primitives'
import { type ButtonHTMLAttributes, type ReactNode, useRef, useState } from 'react'
import s from './ui-kit.module.css'

// ---------------------------------------------------------------------------
// 1. IconButton — 28px (md) or 24px (sm) square icon button
// ---------------------------------------------------------------------------

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  size?: 'md' | 'sm'
  active?: boolean
  danger?: boolean
}

export function IconButton({
  size = 'md',
  active = false,
  danger = false,
  className,
  children,
  ...rest
}: IconButtonProps) {
  const cls = [
    s.iconBtn,
    size === 'sm' ? s.iconBtnSm : '',
    active ? s.iconBtnActive : '',
    danger ? s.iconBtnDanger : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button type="button" className={cls} {...rest}>
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// 2. Chip — 22px pill filter with optional count badge
// ---------------------------------------------------------------------------

export interface ChipProps {
  active?: boolean
  count?: number
  onClick?: () => void
  children: ReactNode
}

export function Chip({ active = false, count, onClick, children }: ChipProps) {
  return (
    <button
      type="button"
      className={`${s.chip} ${active ? s.chipActive : ''}`}
      onClick={onClick}
    >
      <span>{children}</span>
      {typeof count === 'number' && <span className={s.chipCount}>{count}</span>}
    </button>
  )
}

// ---------------------------------------------------------------------------
// 3. SectionHeader — 28px sub-panel header band with count + right actions
// ---------------------------------------------------------------------------

export interface SectionHeaderProps {
  label: ReactNode
  count?: number
  action?: ReactNode
}

export function SectionHeader({ label, count, action }: SectionHeaderProps) {
  return (
    <div className={s.sectionHeader}>
      <div className={s.sectionHeaderLeft}>
        <span className={s.sectionHeaderLabel}>{label}</span>
        {typeof count === 'number' && <span className={s.sectionHeaderCount}>{count}</span>}
      </div>
      {action && <div className={s.sectionHeaderRight}>{action}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// 4. Notice — Unified empty / loading / error / warn / hint state block
// ---------------------------------------------------------------------------

export interface NoticeProps {
  kind?: 'empty' | 'loading' | 'error' | 'warn' | 'hint'
  tone?: 'page' | 'well' | 'inline'
  title?: ReactNode
  detail?: ReactNode
  action?: ReactNode
}

export function Notice({
  kind = 'empty',
  tone = 'well',
  title,
  detail,
  action,
}: NoticeProps) {
  const cls = [
    s.notice,
    tone === 'page' ? s.noticePage : tone === 'inline' ? s.noticeInline : s.noticeWell,
    kind === 'error' ? s.noticeError : kind === 'warn' ? s.noticeWarn : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={cls} role={kind === 'error' ? 'alert' : 'status'}>
      {kind === 'loading' && <span className={s.noticeSpinner} aria-hidden="true" />}
      {title && <div className={s.noticeTitle}>{title}</div>}
      {detail && <div className={s.noticeDetail}>{detail}</div>}
      {action && <div>{action}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// 5. StatusBadge — Semantic tone badge (`neutral | info | success | warn | error`)
// ---------------------------------------------------------------------------

export interface StatusBadgeProps {
  tone?: 'neutral' | 'info' | 'success' | 'warn' | 'error'
  children: ReactNode
}

export function StatusBadge({ tone = 'neutral', children }: StatusBadgeProps) {
  return (
    <span className={s.statusBadge} data-tone={tone}>
      {children}
    </span>
  )
}

// ---------------------------------------------------------------------------
// 6. Switch — Accessible toggle switch bound to DSH skin tokens
// ---------------------------------------------------------------------------

export interface SwitchProps {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  ariaLabel?: string
}

export function Switch({ checked, onChange, disabled = false, ariaLabel }: SwitchProps) {
  return (
    <label className={s.switchRoot}>
      <input
        type="checkbox"
        className={s.switchInput}
        checked={checked}
        disabled={disabled}
        aria-label={ariaLabel}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className={s.switchTrack}>
        <span className={s.switchThumb} />
      </span>
    </label>
  )
}

// ---------------------------------------------------------------------------
// 7. ConfirmDialog — Host `Modal` + `Button` confirmation wrapper
//    Note: Only mount `Modal` when `open` is true for SSR / hook safety.
// ---------------------------------------------------------------------------

export interface ConfirmDialogProps {
  open: boolean
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onClose: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  if (!open) return null
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      closeLabel={cancelLabel}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            {cancelLabel}
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              onConfirm()
              onClose()
            }}
          >
            {confirmLabel}
          </Button>
        </>
      }
    />
  )
}

// ---------------------------------------------------------------------------
// 8. SelectMenu — Trigger button + Host `Menu` dropdown
// ---------------------------------------------------------------------------

export interface SelectMenuProps {
  value: string
  items: MenuItem[]
  onSelect: (id: string) => void
}

export function SelectMenu({ value, items, onSelect }: SelectMenuProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const current = items.find((item) => item.id === value)

  return (
    <>
      <Button
        ref={triggerRef}
        variant="outline"
        onClick={() => setOpen((prev) => !prev)}
      >
        <span>{current?.label ?? value}</span>
        <IconChevronDownOutlineRegular size={14} />
      </Button>
      <Menu
        open={open}
        anchor={triggerRef.current}
        items={items}
        selectedId={value}
        onSelect={(id) => {
          onSelect(id)
          setOpen(false)
        }}
        onClose={() => setOpen(false)}
        portal
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// 9. FeatureCard — Toggleable feature card with bottom gear settings strip
// ---------------------------------------------------------------------------

export interface FeatureCardProps {
  title: string
  description: string
  enabled: boolean
  onToggle: (next: boolean) => void
  onOpenSettings?: () => void
}

export function FeatureCard({
  title,
  description,
  enabled,
  onToggle,
  onOpenSettings,
}: FeatureCardProps) {
  return (
    <div className={`${s.featureCard} ${enabled ? s.featureCardActive : ''}`}>
      <div className={s.featureCardTop}>
        <div>
          <div className={s.featureCardTitle}>{title}</div>
          <div className={s.featureCardDesc}>{description}</div>
        </div>
        <Switch checked={enabled} onChange={onToggle} ariaLabel={`Toggle ${title}`} />
      </div>
      {onOpenSettings && (
        <div className={s.featureCardFooter}>
          <StatusBadge tone={enabled ? 'success' : 'neutral'}>
            {enabled ? 'Enabled' : 'Disabled'}
          </StatusBadge>
          <IconButton
            size="sm"
            aria-label={`Configure ${title}`}
            onClick={onOpenSettings}
          >
            <IconSettingsOutlineRegular size={14} />
          </IconButton>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// 10. Skin Token Opacity Guard (for Monaco / xterm / canvas surfaces)
//     Glass skins (`glass-Aurora`, `glass-Frost`) set `--dsw-alias-bg-base` to
//     translucent rgba values (~0.56 alpha) which canvas renderers reject or
//     render unreadably. Clamp alpha < 0.9 to a solid fallback.
// ---------------------------------------------------------------------------

export function ensureOpaqueSurface(tokenName: string, fallbackHex: string): string {
  if (typeof document === 'undefined') return fallbackHex
  const raw = getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim()
  if (!raw) return fallbackHex
  const rgbaMatch = raw.match(/^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)$/i)
  if (rgbaMatch) {
    const alpha = Number.parseFloat(rgbaMatch[4])
    if (alpha < 0.9) return fallbackHex
  }
  return raw
}
