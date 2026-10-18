'use client';

import { DndContext, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors } from '@dnd-kit/core';
import type { ReactNode } from 'react';

type Target = { employeeId: string; day: number };

export function RosterDragContext({ children, onMove }: { children: ReactNode; onMove: (shiftId: string, target: Target) => void }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { keyboardCodes: { start: ['Space'], cancel: ['Escape'], end: ['Space'] } }),
  );
  return <DndContext id="sandbox-roster" sensors={sensors} onDragEnd={({ active, over }) => {
    const target = over?.data.current as Target | undefined;
    if (target) onMove(String(active.id), target);
  }}>{children}</DndContext>;
}

export function DraggableShift({ id, locked, className, onClick, label, children }: { id: string; locked: boolean; className: string; onClick: () => void; label: string; children: ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id, disabled: locked });
  return <button ref={setNodeRef} {...attributes} {...listeners} aria-disabled={false} className={className} aria-label={label} onClick={() => { if (!isDragging) onClick(); }} style={{ transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined, position: 'relative', zIndex: isDragging ? 5 : undefined, opacity: isDragging ? .7 : 1, touchAction: 'pan-y' }}>{children}</button>;
}

export function EmptyRosterCell({ employeeId, day, label, onClick, children }: Target & { label: string; onClick: () => void; children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: `${employeeId}:${day}`, data: { employeeId, day } });
  return <button ref={setNodeRef} className={`off-day ${isOver ? 'drop-target' : ''}`} aria-label={label} onClick={onClick}>{children}</button>;
}
