"use client";

// Semáforo de una tarea: punto de color + texto (nunca solo color). Los textos y el nivel salen de lib/neuralLenguaSimple.
import type { EstadoTarea, TareaId } from "../lib/neural";
import { SEMAFORO, nivelTarea } from "../lib/neuralLenguaSimple";

export function Semaforo({ tarea, estado }: { tarea: TareaId; estado: EstadoTarea }) {
  const s = SEMAFORO[nivelTarea(tarea, estado)];
  return (
    <span title={s.ayuda} className="inline-flex items-center gap-1.5 whitespace-nowrap rounded border border-[var(--boveda-linea-fuerte)] px-2 py-0.5 text-xs font-semibold text-[var(--portal-fg)]">
      <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
      {s.titulo}
    </span>
  );
}
