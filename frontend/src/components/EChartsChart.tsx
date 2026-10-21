"use client";

import { useEffect, useRef, useState } from "react";
import { PALETA } from "@/lib/paleta";

// Apache ECharts (open-source) desde el CDN gratuito jsDelivr. Sin npm install.
// BLINDAJE (Lote C): versión EXACTA (no rango @5) + SRI sha384 + crossorigin. Si jsDelivr
// sirviera bytes distintos a este hash, el navegador BLOQUEA la ejecución (anti-supply-chain).
// Para actualizar la versión hay que recomputar el hash:
//   curl -fsSL <url> | openssl dgst -sha384 -binary | openssl base64 -A
const ECHARTS_VERSION = "5.5.1";
const ECHARTS_SRC = `https://cdn.jsdelivr.net/npm/echarts@${ECHARTS_VERSION}/dist/echarts.min.js`;
const ECHARTS_SRI = "sha384-Mx5lkUEQPM1pOJCwFtUICyX45KNojXbkWdYhkKUKsbv391mavbfoAmONbzkgYPzR";

interface ZrEvent {
  offsetX: number;
  offsetY: number;
}
interface ZrHandler {
  on: (event: string, handler: (params: ZrEvent) => void) => void;
  off: (event: string, handler?: (params: ZrEvent) => void) => void;
}
export interface EChartsInstance {
  setOption: (option: Record<string, unknown>, notMerge?: boolean) => void;
  resize: () => void;
  dispose: () => void;
  on: (event: string, handler: (params: unknown) => void) => void;
  off: (event: string, handler?: (params: unknown) => void) => void;
  getZr: () => ZrHandler;
  convertFromPixel: (finder: Record<string, unknown>, value: number[]) => number[];
  containPixel: (finder: Record<string, unknown>, value: number[]) => boolean;
}
interface EChartsLib {
  init: (el: HTMLElement, theme?: string | null, opts?: { renderer?: "canvas" | "svg" }) => EChartsInstance;
  registerTheme: (name: string, theme: Record<string, unknown>) => void;
}
type WindowWithECharts = Window & { echarts?: EChartsLib };

// Tema "dashboard avanzado" aplicado a TODOS los gráficos (paleta categórica + ejes, tooltip, leyenda
// y series refinados sobre fondo oscuro, inspirado en galerías open-source tipo Tremor/ECharts). Las
// opciones por-gráfico siguen mandando sobre el tema donde definen su propio estilo (no rompe nada).
const TORRE_THEME: Record<string, unknown> = {
  color: [PALETA.azul, PALETA.adverso, PALETA.serie3, PALETA.azulClaro, PALETA.tierraClara, PALETA.serie4, PALETA.neutro, PALETA.tierra],
  backgroundColor: "transparent",
  textStyle: { color: PALETA.muted },
  title: { textStyle: { color: PALETA.fg, fontWeight: 600 }, subtextStyle: { color: PALETA.muted } },
  legend: { textStyle: { color: PALETA.muted }, inactiveColor: PALETA.subtle, icon: "roundRect" },
  tooltip: {
    backgroundColor: "#232528",
    borderColor: "rgba(201,162,94,0.25)",
    borderWidth: 1,
    borderRadius: 3,
    padding: [8, 12],
    textStyle: { color: PALETA.fg, fontSize: 12 },
    axisPointer: { lineStyle: { color: "rgba(237,237,239,0.3)" }, crossStyle: { color: "rgba(237,237,239,0.3)" } },
    // Nunca dejar el tooltip flotando fuera de la caja del gráfico (p.ej. si el
    // canvas quedó a medio redimensionar): se confina al contenedor del chart.
    confine: true,
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: PALETA.lineaFuerte } },
    axisTick: { show: false },
    axisLabel: { color: PALETA.muted },
    splitLine: { show: false, lineStyle: { color: PALETA.linea } },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: PALETA.muted },
    splitLine: { lineStyle: { color: PALETA.linea } },
  },
  line: { smooth: true, symbol: "circle", symbolSize: 6, lineStyle: { width: 2.5 } },
  bar: { itemStyle: { borderRadius: [1, 1, 0, 0] } },
  pie: { itemStyle: { borderColor: PALETA.panel, borderWidth: 2 } },
};
let themeRegistered = false;

let loaderPromise: Promise<EChartsLib> | null = null;

function loadECharts(): Promise<EChartsLib> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("SSR"));
  }
  const existingLib = (window as WindowWithECharts).echarts;
  if (existingLib) {
    return Promise.resolve(existingLib);
  }
  if (loaderPromise) {
    return loaderPromise;
  }
  loaderPromise = new Promise<EChartsLib>((resolve, reject) => {
    const finish = () => {
      const lib = (window as WindowWithECharts).echarts;
      if (lib) {
        resolve(lib);
      } else {
        reject(new Error("ECharts no disponible tras cargar el script."));
      }
    };
    const existing = document.querySelector('script[data-echarts="true"]');
    if (existing) {
      existing.addEventListener("load", finish);
      existing.addEventListener("error", () => reject(new Error("No se pudo cargar ECharts.")));
      return;
    }
    const script = document.createElement("script");
    script.src = ECHARTS_SRC;
    script.async = true;
    // SRI: el navegador verifica el hash antes de ejecutar; crossOrigin=anonymous es
    // requisito para que integrity aplique a un recurso de otro origen (CORS).
    script.integrity = ECHARTS_SRI;
    script.crossOrigin = "anonymous";
    script.setAttribute("data-echarts", "true");
    script.addEventListener("load", finish);
    script.addEventListener("error", () => reject(new Error("No se pudo cargar ECharts.")));
    document.head.appendChild(script);
  });
  return loaderPromise;
}

// Altura EFECTIVA responsive (sin tocar la API pública: los paneles siguen pasando
// `height` como px "de escritorio"). En pantallas chicas el alto fijo (340-560px) o
// proporcional al nº de filas (miles de px) no cabe — sobre todo en landscape móvil
// (~390px de alto), donde un solo chart tapa la pantalla. Acotamos el alto del
// contenedor a un TOPE por viewport y, si el `height` pedido lo supera, el gráfico
// vive dentro de una caja con scroll interno (nunca desborda ni empuja la página).
//
// Reglas del tope:
//  - Viewport ANCHO (>= 900px, escritorio/tablet horizontal): NO se aplica tope →
//    `height` se respeta EXACTO como hoy (no rompe desktop aprobado).
//  - Landscape de poca altura (alto <= 500px): el chart no debe pasar de ~85dvh, y
//    además nunca más de (alto de viewport - 6rem) para dejar aire al resto.
//  - Móvil portrait (ancho < 900px, alto > 500px): tope de ~70dvh para que un chart
//    alto no ocupe más que la pantalla; el resto se ve por scroll interno.
// Devuelve el `height` original si no hay ventana (SSR) o si el viewport es amplio.
function computeEffectiveHeight(requested: number): number {
  if (typeof window === "undefined") {
    return requested;
  }
  const vw = window.innerWidth || 0;
  const vh = window.innerHeight || 0;
  if (vw >= 900 || vh <= 0) {
    // Escritorio / tablet horizontal: sin tope, comportamiento idéntico al actual.
    return requested;
  }
  // rem→px (16px si no hay contexto). Reservamos margen para cabecera/controles.
  const rem = 16;
  let cap: number;
  if (vh <= 500) {
    // Landscape móvil: lo más agresivo — cabe dentro de la pantalla con holgura.
    cap = Math.min(vh * 0.85, vh - 6 * rem);
  } else {
    // Portrait móvil / pantalla chica vertical: ~70% del alto visible.
    cap = vh * 0.7;
  }
  // Piso de seguridad: nunca por debajo de 180px (un chart legible mínimo), y nunca
  // por encima del alto pedido (en desktop-como-móvil pequeño el pedido puede ser < cap).
  cap = Math.max(cap, 180);
  return Math.min(requested, Math.round(cap));
}

export function EChartsChart({
  option,
  height = 300,
  className,
  ariaLabel,
  onEvents,
  onReady,
}: {
  option: Record<string, unknown>;
  height?: number;
  className?: string;
  ariaLabel?: string;
  onEvents?: Record<string, (params: unknown) => void>;
  // Se llama UNA vez con la instancia ECharts ya inicializada (para interacciones que
  // necesitan la instancia: clic por pixel→dato, brush, etc.). Aditivo y opcional.
  onReady?: (chart: EChartsInstance) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsInstance | null>(null);
  const [visible, setVisible] = useState(false);
  const [ready, setReady] = useState(false);
  // Alto efectivo (px) del contenedor visible. Arranca con el pedido (SSR-safe) y se
  // recalcula en el cliente al montar y en cada cambio de viewport/orientación.
  const [effHeight, setEffHeight] = useState<number>(height);

  // Lazy: solo cargamos/inicializamos cuando el contenedor entra en viewport.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            io.disconnect();
          }
        }
      },
      { rootMargin: "140px" },
    );
    io.observe(el);
    // Respaldo: si el observador no dispara (ocurre en vistas embebidas o contenedores
    // transformados donde IntersectionObserver no entrega entradas) pero el contenedor está
    // dentro del viewport ampliado, se inicializa igual. Sin esto el gráfico queda en
    // blanco sin ningún error que lo delate.
    let ventana: number | null = null;
    const enViewport = () => {
      const r = el.getBoundingClientRect();
      return r.bottom > -140 && r.top < window.innerHeight + 140;
    };
    const activar = () => {
      setVisible(true);
      io.disconnect();
      window.removeEventListener("scroll", alScroll);
      window.removeEventListener("resize", alScroll);
    };
    const alScroll = () => {
      if (ventana !== null) return;
      ventana = window.setTimeout(() => {
        ventana = null;
        if (enViewport()) activar();
      }, 200);
    };
    const respaldo = window.setTimeout(() => {
      if (enViewport()) activar();
    }, 1500);
    window.addEventListener("scroll", alScroll, { passive: true });
    window.addEventListener("resize", alScroll);
    return () => {
      io.disconnect();
      window.clearTimeout(respaldo);
      if (ventana !== null) window.clearTimeout(ventana);
      window.removeEventListener("scroll", alScroll);
      window.removeEventListener("resize", alScroll);
    };
  }, []);

  // Recalcula el alto efectivo al montar (cliente) y cuando cambia el viewport o la
  // orientación. Al cambiar `effHeight`, el div externo cambia de alto → el
  // ResizeObserver de abajo dispara chart.resize(); igualmente forzamos un resize por
  // si el alto efectivo no cambió pero sí el ancho (p.ej. rotación con misma altura).
  useEffect(() => {
    const recompute = () => {
      const next = computeEffectiveHeight(height);
      setEffHeight((prev) => (prev === next ? prev : next));
      if (chartRef.current) {
        chartRef.current.resize();
      }
    };
    recompute();
    if (typeof window === "undefined") {
      return;
    }
    window.addEventListener("resize", recompute);
    window.addEventListener("orientationchange", recompute);
    return () => {
      window.removeEventListener("resize", recompute);
      window.removeEventListener("orientationchange", recompute);
    };
  }, [height]);

  useEffect(() => {
    if (!visible) {
      return;
    }
    let disposed = false;
    let ro: ResizeObserver | null = null;
    let onResize: (() => void) | null = null;
    loadECharts()
      .then((echarts) => {
        if (disposed || !containerRef.current) {
          return;
        }
        if (!themeRegistered) {
          echarts.registerTheme("torre", TORRE_THEME);
          themeRegistered = true;
        }
        const chart = echarts.init(containerRef.current, "torre", { renderer: "canvas" });
        chartRef.current = chart;
        chart.setOption(option, true);
        if (onEvents) {
          for (const [ev, handler] of Object.entries(onEvents)) {
            chart.on(ev, handler);
          }
        }
        if (onReady) {
          onReady(chart);
        }
        setReady(true);
        // Responsive real: redimensiona el canvas cuando el CONTENEDOR cambia de tamaño por
        // CUALQUIER causa (ancho por el layout/breakpoint, alto por la prop dinámica al filtrar
        // datos), no solo en window.resize. Sin esto el canvas mantiene su tamaño inicial y, si
        // queda más alto que el contenedor, desborda y se encima con lo de abajo (tabla/otros).
        if (typeof ResizeObserver !== "undefined" && containerRef.current) {
          ro = new ResizeObserver(() => chart.resize());
          ro.observe(containerRef.current);
        } else {
          onResize = () => chart.resize();
          window.addEventListener("resize", onResize);
        }
      })
      .catch(() => {
        /* CDN bloqueado/offline: queda el contenedor con su aria-label. */
      });
    return () => {
      disposed = true;
      if (ro) {
        ro.disconnect();
      }
      if (onResize) {
        window.removeEventListener("resize", onResize);
      }
      if (chartRef.current) {
        chartRef.current.dispose();
        chartRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.setOption(option, true);
    }
  }, [option]);

  // Re-vincula los manejadores de eventos cuando cambian (capturan props frescas).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onEvents) {
      return;
    }
    for (const [ev, handler] of Object.entries(onEvents)) {
      chart.off(ev);
      chart.on(ev, handler);
    }
    return () => {
      const c = chartRef.current;
      if (c && onEvents) {
        for (const ev of Object.keys(onEvents)) {
          c.off(ev);
        }
      }
    };
  }, [onEvents, ready]);

  // ¿El alto pedido excede MUCHO el tope (chart proporcional a nº de filas, miles de
  // px)? Entonces conservamos su alto real y lo hacemos scrolleable dentro de la caja
  // acotada — así las barras/filas siguen legibles. Si solo lo excede un poco (chart de
  // alto fijo 340-560px), dejamos que ECharts encoja para caber sin scroll.
  const capped = effHeight < height;
  const scrollInside = capped && height > effHeight * 1.6;
  // Alto del lienzo interno: el pedido cuando scrolleamos; el acotado cuando encoge.
  const innerHeight = scrollInside ? height : "100%";

  return (
    <div
      className={className}
      style={{
        position: "relative",
        height: effHeight,
        // La caja nunca desborda la página en X; si el chart es más alto que el tope
        // (proporcional a filas), se scrollea en Y dentro de su propia caja.
        maxWidth: "100%",
        width: "100%",
        overflowX: "hidden",
        overflowY: scrollInside ? "auto" : "hidden",
      }}
    >
      <div ref={containerRef} style={{ height: innerHeight, width: "100%" }} role="img" aria-label={ariaLabel} />
      {ready ? null : <div className="portal-skeleton" aria-hidden="true" />}
    </div>
  );
}
