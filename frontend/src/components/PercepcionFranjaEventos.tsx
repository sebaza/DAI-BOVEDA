"use client";

/**
 * Banda de contexto del calendario — UNA sola banda pegada al eje X.
 *
 * POR QUÉ SE ABANDONARON LOS CARRILES
 * -----------------------------------
 * La versión anterior daba un carril a cada categoría. Con seis categorías y ~30 px
 * de alto disponible, cada carril quedaba en 8-11 px y el conjunto se leía como un
 * código de barras: mucha tinta, poca información. El espacio vertical no da para
 * seis filas, y forzarlo hacía que la banda compitiera con la serie en vez de
 * acompañarla.
 *
 * DOS LENGUAJES VISUALES, NO SEIS FILAS
 * -------------------------------------
 * Lo que distingue a un evento no es su categoría sino su NATURALEZA:
 *
 *   BARRA      lo que DURA — semestre, receso, paro. Un tramo de tiempo.
 *   MARCADOR   lo que OCURRE — una emergencia, un cierre de matrícula. Un instante.
 *
 * Dibujar los dos igual obligaba a leer la leyenda para saber cuál era cuál. Con dos
 * formas distintas, la banda se entiende sin leyenda: rectángulos largos abajo,
 * rombos y ticks arriba.
 *
 * La clasificación NO es fija por categoría: un evento con duración cuyo tramo
 * renderiza menos de `MIN_PX_BARRA` se dibuja como marcador igual. Un examen de cinco
 * días sobre cuatro años de eje es un punto, y pintarlo como barra de 1 px es
 * pretender una precisión que la pantalla no tiene. Al filtrar a 30 días, ese mismo
 * examen vuelve a ser barra solo.
 *
 * AGRUPACIÓN
 * ----------
 * Los marcadores que caen a menos de `AGRUPAR_PX` se funden en uno con contador. Sin
 * eso, los 35 hitos de matrícula formaban una línea continua de puntos donde no se
 * distinguía ninguno — que es justamente el efecto código de barras.
 *
 * UN SOLO CONTROL
 * ---------------
 * Qué categorías se ven lo deciden los toggles de «Marcas», debajo del gráfico, y
 * esta banda recibe los eventos YA filtrados. Antes tenía su propio estado y podían
 * discrepar: la banda mostraba algo que el gráfico no, y no había forma de saber
 * cuál de los dos controles mandaba.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { PALETA } from "@/lib/paleta";

import type { EventoItem } from "../lib/percepcion";

type Forma = "barra" | "marcador";

type Categoria = {
  clave: string;
  etiqueta: string;
  color: string;
  /** Cómo se dibuja por naturaleza; un tramo muy corto igual cae a marcador. */
  forma: Forma;
  /** Símbolo del marcador. */
  simbolo?: "rombo" | "tick";
  /** Orden de pintado: lo que interrumpe va arriba. */
  z: number;
  tipos: string[];
};

export const CATEGORIAS_EVENTO: Categoria[] = [
  // Original per-category hues, kept outside the brand palette so each category stays distinct.
  { clave: "paro", etiqueta: "Paro o toma", color: "#f2777a", forma: "barra", z: 5, tipos: ["paro", "toma"] },
  { clave: "emergencia", etiqueta: "Emergencia", color: "#fb923c", forma: "marcador", simbolo: "rombo", z: 6, tipos: ["emergencia"] },
  { clave: "sinclases", etiqueta: "Recesos", color: "#4f9cf0", forma: "barra", z: 3, tipos: ["receso", "fiestas_patrias"] },
  { clave: "semestre", etiqueta: "Semestre", color: "#51c28c", forma: "barra", z: 1, tipos: ["semestre"] },
  { clave: "evaluacion", etiqueta: "Evaluaciones", color: "#e0aa4e", forma: "marcador", simbolo: "rombo", z: 4, tipos: ["examenes"] },
  { clave: "hitos", etiqueta: "Matrícula y anuncios", color: "#a88bfa", forma: "marcador", simbolo: "tick", z: 2, tipos: ["otro", "cambio_calendario", "resolucion"] },
];

const POR_TIPO = new Map<string, Categoria>();
CATEGORIAS_EVENTO.forEach((c) => c.tipos.forEach((t) => POR_TIPO.set(t, c)));
const OTROS = CATEGORIAS_EVENTO[CATEGORIAS_EVENTO.length - 1];

/** La categoría de un tipo de evento. Única fuente de verdad del agrupado. */
export function categoriaDeTipo(tipo: string): Categoria {
  return POR_TIPO.get(tipo) ?? OTROS;
}

/**
 * Todos los tipos conocidos, para que el panel arme su estado de toggles sin
 * duplicar la tabla. Qué arranca encendido lo decide `TIPOS_APAGADOS_AL_INICIO`
 * allá: es UNA sola fuente, y así el gráfico y esta banda no pueden discrepar.
 */
export const TIPOS_CONOCIDOS = CATEGORIAS_EVENTO.flatMap((c) => c.tipos);

const ALTO = 18;            // banda abierta: dos franjas de 8 px + separación
const ALTO_PLEGADA = 5;
const ALTO_BARRA = 7;       // los tramos largos, abajo
const MIN_PX_BARRA = 5;     // por debajo, un tramo se dibuja como marcador
const AGRUPAR_PX = 8;       // marcadores más cerca que esto se funden
const DIA_MS = 86_400_000;

// Ancho de la línea de un evento corto. Un paro de un día sobre cuatro años de eje
// mide 0,06 % del ancho: con `Math.max(0.3, ...)` quedaba en ~1,5 px translúcido,
// o sea invisible. Y un rombo de 6 px arriba tampoco alcanzaba para ver DÓNDE cae.
//
// Ahora un evento corto se dibuja como una línea vertical de 2 px que cruza TODA la
// banda: es la marca más angosta que se sigue leyendo, y su altura completa la ancla
// a la fecha sin ambigüedad. El símbolo (rombo o tick) va encima, como remate.
const ANCHO_LINEA_CORTA = 2;

function dia(iso: string): number {
  return new Date(`${iso}T00:00:00`).getTime();
}

function duracionTexto(ini: string, fin: string | null | undefined): string {
  if (!fin || fin === ini) return "1 día";
  const d = Math.round((dia(fin) - dia(ini)) / DIA_MS) + 1;
  return d >= 14 ? `${d} días (${Math.round(d / 7)} semanas)` : `${d} días`;
}

type Item = {
  cat: Categoria;
  ini: number;
  fin: number;
  detalle: string[];
};

/** Fecha ISO de un timestamp, sin desfase de zona horaria. */
function iso(ts: number): string {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function PercepcionFranjaEventos({
  eventos, desde, hasta, onSeleccionRango, seleccion, pasoDias = 1,
}: {
  eventos: EventoItem[];
  /** Extremos del eje del gráfico de arriba, para quedar alineados.
   *
   * ⚠️ Tienen que venir de la serie AGRUPADA, no de la cruda: `agruparSerie` ancla
   * los bloques a una época fija, así que el primer bloque empieza antes del primer
   * punto diario (hasta 6 días con paso semanal, 29 con mensual). Con los extremos
   * crudos, un paro quedaba dibujado corrido respecto de la caída que lo acompaña. */
  desde?: string;
  hasta?: string;
  /** Cada cuántos días agrega el gráfico de arriba.
   *
   * La franja lo necesita para AGRUPAR CON EL MISMO CRITERIO. Hasta ahora juntaba
   * marcadores por cercanía en PÍXELES, que es una regla distinta de la del gráfico:
   * podían verse dos marcas separadas donde la curva tenía un solo punto, y esa
   * discrepancia es justo lo que hace que las dos bandas se lean desincronizadas.
   * Dos eventos que caen en el mismo bloque son, para el gráfico, el mismo momento. */
  pasoDias?: number;
  /**
   * Clic en una marca → filtra TODO el tablero a ese rango. Es lo que convierte la
   * banda de contexto en un control: ver que hubo un paro y poder leer qué se dijo
   * durante él son dos cosas distintas, y hasta ahora había que copiar las fechas a
   * mano en los selectores de abajo.
   */
  onSeleccionRango?: (desde: string, hasta: string) => void;
  /** Rango activo del tablero, para resaltar la marca que lo produjo. */
  seleccion?: { desde?: string; hasta?: string };
}) {
  const [abierta, setAbierta] = useState(false);
  // El ancho real hace falta para decidir barra vs marcador y para agrupar: ambas
  // cosas se miden en PÍXELES, no en porcentaje del rango.
  const [ancho, setAncho] = useState(0);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setAncho(e.contentRect.width));
    ro.observe(el);
    setAncho(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const { barras, marcadores, conteos, total } = useMemo(() => {
    const vacio = { barras: [], marcadores: [], conteos: {} as Record<string, number>, total: 0 };
    if (!desde || !hasta || ancho <= 0) return vacio;
    const t0 = dia(desde);
    const t1 = dia(hasta);
    const span = Math.max(1, t1 - t0);
    const pxPorMs = ancho / span;

    const dentro = eventos.filter((e) => {
      const ini = dia(e.fecha_inicio);
      const fin = dia(e.fecha_fin ?? e.fecha_inicio);
      return fin >= t0 && ini <= t1;
    });

    const cuenta: Record<string, number> = {};
    for (const e of dentro) {
      const cat = categoriaDeTipo(e.tipo);
      cuenta[cat.clave] = (cuenta[cat.clave] ?? 0) + 1;
    }

    const items: Item[] = dentro
      .map((e) => {
        const cat = categoriaDeTipo(e.tipo);
        const rango =
          e.fecha_fin && e.fecha_fin !== e.fecha_inicio
            ? `${e.fecha_inicio} → ${e.fecha_fin}`
            : e.fecha_inicio;
        return {
          cat,
          ini: Math.max(dia(e.fecha_inicio), t0),
          fin: Math.min(dia(e.fecha_fin ?? e.fecha_inicio), t1),
          detalle: [
            `${e.nombre}\n   ${rango} · ${duracionTexto(e.fecha_inicio, e.fecha_fin)}` +
              (e.ambito && e.ambito !== "global" ? ` · ${e.ambito}` : "") +
              (e.confianza && e.confianza !== "confirmado" ? ` · fecha ${e.confianza}` : ""),
          ],
        };
      });

    // Un tramo que no llega a MIN_PX_BARRA no se puede dibujar como barra sin fingir
    // una precisión que la pantalla no tiene: pasa a marcador.
    const esBarra = (it: Item) =>
      it.cat.forma === "barra" && (it.fin - it.ini) * pxPorMs >= MIN_PX_BARRA;

    // --- BARRAS: se fusionan las solapadas o consecutivas de la misma categoría ---
    const crudas = items.filter(esBarra).sort((a, b) => a.ini - b.ini);
    const fusion: Item[] = [];
    for (const it of crudas) {
      const prev = fusion[fusion.length - 1];
      if (prev && prev.cat.clave === it.cat.clave && it.ini <= prev.fin + DIA_MS) {
        prev.fin = Math.max(prev.fin, it.fin);
        prev.detalle.push(...it.detalle);
        continue;
      }
      fusion.push({ ...it, detalle: [...it.detalle] });
    }
    const barrasOut = fusion
      .map((t, i) => ({
        id: `b-${t.cat.clave}-${t.ini}-${i}`,
        clave: t.cat.clave,
        color: t.cat.color,
        z: t.cat.z,
        izq: ((t.ini - t0) / span) * 100,
        ancho: Math.max(0.3, ((t.fin - t.ini) / span) * 100),
        desde: iso(t.ini),
        hasta: iso(t.fin),
        titulo: `${t.cat.etiqueta}\n${t.detalle.join("\n")}\n\n→ clic para ver el tablero de este período`,
      }))
      .sort((a, b) => a.z - b.z);

    // --- MARCADORES: los cercanos de una misma categoría se agrupan con contador ---
    const puntuales = items.filter((it) => !esBarra(it)).sort((a, b) => a.ini - b.ini);
    const grupos: { cat: Categoria; ini: number; fin: number; detalle: string[]; n: number }[] = [];
    // Dos criterios, y basta con que se cumpla UNO:
    //   * cercanía en PÍXELES — las marcas se pisarían en pantalla;
    //   * mismo BLOQUE del gráfico — para la curva de arriba son el mismo momento,
    //     así que mostrarlos separados abajo es prometer una resolución que el
    //     gráfico no tiene. Es lo que sincroniza las dos bandas.
    const pasoMs = Math.max(1, pasoDias) * DIA_MS;
    for (const it of puntuales) {
      const prev = grupos.find(
        (g) =>
          g.cat.clave === it.cat.clave &&
          ((it.ini - g.ini) * pxPorMs < AGRUPAR_PX || it.ini - g.ini < pasoMs),
      );
      if (prev) {
        prev.fin = Math.max(prev.fin, it.fin);
        prev.detalle.push(...it.detalle);
        prev.n += 1;
        continue;
      }
      grupos.push({ cat: it.cat, ini: it.ini, fin: it.fin, detalle: [...it.detalle], n: 1 });
    }
    const marcadoresOut = grupos
      .map((g, i) => ({
        id: `m-${g.cat.clave}-${g.ini}-${i}`,
        clave: g.cat.clave,
        color: g.cat.color,
        simbolo: g.cat.simbolo ?? "rombo",
        z: g.cat.z,
        izq: ((g.ini - t0) / span) * 100,
        n: g.n,
        desde: iso(g.ini),
        hasta: iso(g.fin),
        titulo:
          `${g.cat.etiqueta}${g.n > 1 ? ` · ${g.n} eventos` : ""}\n${g.detalle.join("\n")}` +
          "\n\n→ clic para ver el tablero de este período",
      }))
      .sort((a, b) => a.z - b.z);

    return { barras: barrasOut, marcadores: marcadoresOut, conteos: cuenta, total: dentro.length };
    // `pasoDias` va en las dependencias: al cambiar la agregación del gráfico, la
    // franja tiene que reagrupar o vuelve a quedar desincronizada.
  }, [eventos, desde, hasta, ancho, pasoDias]);

  if (!desde || !hasta) return null;

  const visibles = CATEGORIAS_EVENTO.filter((c) => conteos[c.clave]);
  /** Porcentaje del rango a píxeles reales, para decidir si algo es visible. */
  const anchoPx = (pct: number) => (pct / 100) * ancho;

  return (
    // Los márgenes replican EXACTAMENTE el grid.left/right del gráfico. Nada puede ir
    // al costado: le robaría ancho al eje y cada evento quedaría corrido de su fecha.
    <div className="-mt-1" style={{ marginLeft: 40, marginRight: 24 }}>
      {abierta ? (
        <ul className="mb-1 flex flex-wrap items-center justify-end gap-x-2 gap-y-0.5">
          {visibles.map((c) => {
            const on = true;   // lo que llega acá ya viene filtrado por «Marcas»
            return (
              <li key={c.clave}>
                <span
                  title={`${c.etiqueta} · se apaga desde «Marcas», debajo del gráfico`}
                  className="flex items-center gap-1 rounded px-1 py-px text-sm leading-4"
                  style={{ color: c.color }}
                >
                  {/* La muestra usa la MISMA forma que la banda: barra o rombo/tick.
                      Un cuadrito igual para todos obligaría a mirar la banda para
                      descubrir cuál es cuál. */}
                  {c.forma === "barra" ? (
                    <span className="h-1.5 w-3 rounded-sm" style={{ background: c.color, opacity: on ? 1 : 0.5 }} />
                  ) : c.simbolo === "tick" ? (
                    <span className="h-2.5 w-0.5" style={{ background: c.color, opacity: on ? 1 : 0.5 }} />
                  ) : (
                    <span className="h-1.5 w-1.5 rotate-45" style={{ background: c.color, opacity: on ? 1 : 0.5 }} />
                  )}
                  {c.etiqueta}
                  <span className="tabular-nums opacity-70">{conteos[c.clave]}</span>
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}

      <div
        ref={ref}
        className="relative w-full overflow-hidden rounded-b-md bg-white/[0.02] transition-all duration-200"
        style={{ height: abierta ? ALTO : ALTO_PLEGADA }}
      >
        {/* BARRAS abajo: son el tramo, el "piso" temporal. */}
        {barras.map((b) => {
          const activa = seleccion?.desde === b.desde && seleccion?.hasta === b.hasta;
          // Una barra que renderiza pocos píxeles se vuelve invisible con la opacidad
          // de contexto. Se le sube la altura a toda la banda y la opacidad al máximo:
          // vale más ver que ese día pasó algo, aunque el tramo sea de un día.
          const finita = anchoPx(b.ancho) < ANCHO_LINEA_CORTA * 2;
          return (
            <button
              key={b.id}
              type="button"
              title={b.titulo}
              onClick={() => onSeleccionRango?.(b.desde, b.hasta)}
              className="absolute rounded-[2px] transition-[filter,opacity]"
              style={{
                left: `${b.izq}%`,
                width: finita ? ANCHO_LINEA_CORTA : `${b.ancho}%`,
                bottom: 0,
                height: !abierta ? ALTO_PLEGADA : finita ? ALTO : ALTO_BARRA,
                background: b.color,
                // El semestre es contexto puro: se ve, no se impone. Un tramo finito
                // no puede darse ese lujo o desaparece.
                opacity: activa || finita ? 1 : b.clave === "semestre" ? 0.28 : 0.7,
                // La marca activa se realza con brillo, no con borde: un borde de 1 px
                // sobre un bloque de 2 px de ancho lo taparía entero.
                filter: activa ? "brightness(1.6)" : undefined,
                boxShadow: activa ? `0 0 4px ${b.color}` : undefined,
                zIndex: activa ? 9 : finita ? b.z + 10 : b.z,
                cursor: onSeleccionRango ? "pointer" : "default",
              }}
            />
          );
        })}

        {/* MARCADORES arriba: son el instante. Cuelgan sobre las barras. */}
        {abierta
          ? marcadores.map((m) => {
              const activa = seleccion?.desde === m.desde && seleccion?.hasta === m.hasta;
              return (
                <button
                  key={m.id}
                  type="button"
                  title={m.titulo}
                  onClick={() => onSeleccionRango?.(m.desde, m.hasta)}
                  // El área clickeable es más ancha que la marca: acertarle a 2 px
                  // con el mouse es pedir demasiado.
                  className="absolute flex h-full w-3 items-start justify-center"
                  style={{
                    left: `calc(${m.izq}% - 6px)`,
                    top: 0,
                    zIndex: activa ? 9 : m.z,
                    cursor: onSeleccionRango ? "pointer" : "default",
                  }}
                >
                  {/* LÍNEA de altura completa: es lo que hace visible un evento de un
                      día. Sin ella la marca quedaba en un rombo de 6 px flotando
                      arriba, sin anclaje claro a su fecha. */}
                  <span
                    className="absolute inset-y-0"
                    style={{
                      width: ANCHO_LINEA_CORTA,
                      background: m.color,
                      opacity: activa ? 1 : 0.8,
                      boxShadow: activa ? `0 0 4px ${m.color}` : undefined,
                    }}
                  />
                  {/* El símbolo remata la línea arriba y dice de qué tipo es. */}
                  {m.simbolo === "rombo" ? (
                    <span
                      className="relative block h-1.5 w-1.5 rotate-45 rounded-[1px]"
                      style={{ background: m.color, boxShadow: `0 0 0 1px ${PALETA.panel}` }}
                    />
                  ) : null}
                  {/* Un grupo se distingue con un punto extra, no con un número: a
                      esta escala un dígito sería ilegible y ensuciaría la banda. */}
                  {m.n > 1 ? (
                    <span
                      className="absolute right-1 top-0 h-1 w-1 rounded-full"
                      style={{ background: m.color }}
                    />
                  ) : null}
                </button>
              );
            })
          : null}
      </div>

      <button
        type="button"
        onClick={() => setAbierta((v) => !v)}
        className="mt-1 rounded border border-white/10 px-2 py-0.5 text-xs text-slate-400 transition hover:border-white/25 hover:text-slate-100"
        aria-expanded={abierta}
      >
        {abierta ? "▾" : "▸"} calendario ({total})
        {abierta ? "" : " · clic para desplegar"}
      </button>
    </div>
  );
}

export default PercepcionFranjaEventos;
