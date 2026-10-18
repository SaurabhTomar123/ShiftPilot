'use client';

import { useEffect, useRef } from 'react';
import { XIcon } from '@phosphor-icons/react';

export function Dialog({ title, children, onClose, wide = false }: { title: string; children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    return () => { dialog?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className={`dialog ${wide ? 'wide' : ''}`} onCancel={event => { event.preventDefault(); close.current(); }} onClick={event => { if (event.target === event.currentTarget) close.current(); }} aria-labelledby="dialog-title">
    <div className="dialog-heading"><h2 id="dialog-title">{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><XIcon size={20} /></button></div>
    {children}
  </dialog>;
}

export function Avatar({ initials, color, small = false }: { initials: string; color: string; small?: boolean }) {
  return <span className={`avatar ${color} ${small ? 'small' : ''}`} aria-hidden="true">{initials}</span>;
}

export function Empty({ title, description, children }: { title: string; description: string; children?: React.ReactNode }) {
  return <div className="empty"><span className="empty-mark" aria-hidden="true">—</span><h3>{title}</h3><p>{description}</p>{children}</div>;
}
