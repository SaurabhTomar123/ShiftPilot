'use client';

import Link from 'next/link';
import { useEffect, useRef, useState, useSyncExternalStore, type Dispatch, type SetStateAction } from 'react';
import { ArrowRightIcon, CalendarBlankIcon, ClockCounterClockwiseIcon, ListChecksIcon, ListIcon, SidebarSimpleIcon, UsersThreeIcon, XIcon } from '@phosphor-icons/react';
import type { Schema } from '@/api/types';
import { Avatar } from './ui';

export type WorkspaceSection = 'schedule' | 'team' | 'demand' | 'history' | 'absences' | 'scenarios' | 'rules';
export type SidebarMotion = 'slide' | 'dissolve' | 'fold';
const subscribe = (notify: () => void) => { const media = matchMedia('(max-width: 900px)'); media.addEventListener('change', notify); return () => media.removeEventListener('change', notify); };

export function WorkspaceNavigation({ me, section, setSection, collapsed, setCollapsed, motion, fixtureMode, version }: { me: Schema['Me']; section: WorkspaceSection; setSection: (section: WorkspaceSection) => void; collapsed: boolean; setCollapsed: Dispatch<SetStateAction<boolean>>; motion: SidebarMotion; fixtureMode: boolean; version: string }) {
  const mobile = useSyncExternalStore(subscribe, () => matchMedia('(max-width: 900px)').matches, () => false);
  const [open, setOpen] = useState(false);
  const aside = useRef<HTMLElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!mobile || !open) return;
    const previous = document.activeElement as HTMLElement | null;
    const opener = trigger.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden'; close.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); }
      if (event.key === 'Tab') {
        const items = Array.from(aside.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href]') ?? []).filter(item => item.getClientRects().length > 0);
        if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1)?.focus(); }
        else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0]?.focus(); }
      }
    };
    document.addEventListener('keydown', keydown);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', keydown); (previous ?? opener)?.focus(); };
  }, [mobile, open]);
  const items = me.role === 'staff' ? [{ id: 'schedule' as const, name: 'Your schedule', icon: CalendarBlankIcon }] : [{ id: 'schedule' as const, name: 'Schedule', icon: CalendarBlankIcon }, { id: 'team' as const, name: 'Employees', icon: UsersThreeIcon }, { id: 'demand' as const, name: 'Staffing', icon: ListChecksIcon }, { id: 'absences' as const, name: 'Repair Inbox', icon: ListChecksIcon }, { id: 'scenarios' as const, name: 'Scenario Lab', icon: ListChecksIcon }, ...(me.capabilities.includes('manage_employees') ? [{ id: 'rules' as const, name: 'Rules', icon: ListChecksIcon }] : []), { id: 'history' as const, name: 'History', icon: ClockCounterClockwiseIcon }];
  return <>
    <button ref={trigger} type="button" className="mobile-menu-toggle" aria-label="Open navigation" aria-expanded={open} aria-controls="workspace-navigation" onClick={() => setOpen(true)}><ListIcon size={23} /></button>
    {mobile && open && <button className="navigation-backdrop" aria-label="Close navigation overlay" onClick={() => setOpen(false)} tabIndex={-1} />}
    <aside ref={aside} id="workspace-navigation" className={`contract-sidebar ${collapsed ? 'sidebar-collapsed' : ''} ${open ? 'mobile-open' : ''}`} data-motion={motion} inert={mobile && !open} role={mobile && open ? 'dialog' : undefined} aria-modal={mobile && open ? true : undefined} aria-label="Workspace navigation">
      <div className="sidebar-control-row"><span className="sidebar-wordmark">Workspace</span><button className="sidebar-toggle desktop-toggle" type="button" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} aria-controls="workspace-navigation" onClick={() => setCollapsed(value => !value)} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}><SidebarSimpleIcon size={21} /></button><button ref={close} className="sidebar-toggle mobile-close" type="button" aria-label="Close navigation" onClick={() => setOpen(false)}><XIcon size={22} /></button></div>
      <div className="sidebar-identity sidebar-fading"><Avatar initials={me.display_name.split(' ').map(n => n[0]).slice(0, 2).join('')} color="sage" /><strong>{me.display_name}</strong><span>{me.org_name}</span></div>
      <nav className="sidebar-destinations" aria-label="Main navigation">{items.map(item => <button key={item.id} type="button" aria-label={item.name} aria-current={section === item.id ? 'page' : undefined} onClick={() => { setSection(item.id); setOpen(false); }}><item.icon size={21} weight={section === item.id ? 'fill' : 'regular'} /><span className="sidebar-nav-label">{item.name}</span></button>)}</nav>
      <div className="sidebar-guide sidebar-fading"><strong>{me.role === 'staff' ? 'Your published week' : 'Before you publish'}</strong><p>{me.role === 'staff' ? 'Check your assignments, outlet and times. Changes to a draft do not change your published schedule.' : 'Check staffing and assignments. Review any issues before approving a plan.'}</p><span>Human approval stays in control.</span></div>
      <Link className="sidebar-sandbox" href="/sandbox" aria-label="Explore the local editing sandbox"><ArrowRightIcon size={18} /><span className="sidebar-nav-label">Editing sandbox</span></Link>
      <small className="sidebar-fading">{fixtureMode ? `Synthetic preview · ${version}` : 'Scheduling API'}<br />{fixtureMode ? 'Changes here do not publish a roster.' : 'The server checks each action.'}</small>
    </aside>
  </>;
}

export function AppearanceControls({ tone, setTone, typography, setTypography, motion, setMotion }: { tone: string; setTone: (tone: string) => void; typography: string; setTypography: (typography: string) => void; motion: SidebarMotion; setMotion: (motion: SidebarMotion) => void }) {
  return <details className="appearance-controls"><summary>Appearance</summary><div><strong>Make the workspace yours</strong><label>Color treatment<select aria-label="Color treatment" value={tone} onChange={e => setTone(e.target.value)}><option value="paprika">Paprika · warm paper</option><option value="ink">Ink · blue pencil</option><option value="olive">Olive · field notes</option></select></label><label>Typography<select aria-label="Typography" value={typography} onChange={e => setTypography(e.target.value)}><option value="workshop">Workshop · Bricolage + Plex</option><option value="editorial">Editorial · Fraunces + Plex</option><option value="plain">Plain · IBM Plex Sans</option></select></label><label>Sidebar transition<select aria-label="Sidebar transition" value={motion} onChange={e => setMotion(e.target.value as SidebarMotion)}><option value="slide">Slide</option><option value="dissolve">Dissolve</option><option value="fold">Fold</option></select></label><p>All three transitions respect reduced motion. These preferences apply to this visit.</p></div></details>;
}
