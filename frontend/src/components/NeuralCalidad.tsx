"use client";

// Pestaña «Calidad de los datos»: primero la respuesta para quien decide (¿los datos pasan los chequeos? ¿qué límites tienen?);
// las cargas por fuente y las tablas de resultados quedan plegadas.
import { neuralApi } from "../lib/neural";
import { CARD, Carga, FILA, Insignia, Metrica, TD, TH, TablaScroll, Titulo, Vacio, entero, useCarga } from "./NeuralUI";

function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
}

export function NeuralCalidad() {
  const estado = useCarga((s) => neuralApi.calidad(s), []);
  return (
    <Carga estado={estado} filas={6} alto="h-8">
      {(d) => {
        const { ok, total, fallidos } = d.auditoria;
        const sinDiferencias = fallidos.length === 0;
        return (
          <div className="space-y-5">
            <section className={CARD} aria-label="Estado de los datos">
              <Titulo sub="Chequeos automáticos de coherencia de los datos cargados.">¿Los datos están en orden?</Titulo>
              <p className="mb-3 flex flex-wrap items-center gap-2 text-base leading-7 text-[var(--portal-fg)]">
                <Insignia tono={sinDiferencias ? "azul" : "aviso"}>{sinDiferencias ? "Sin diferencias" : "Hay diferencias por revisar"}</Insignia>
                {sinDiferencias
                  ? `Los datos aprobaron ${entero(ok)} de ${entero(total)} chequeos.`
                  : `Los datos aprobaron ${entero(ok)} de ${entero(total)} chequeos; ${entero(fallidos.length)} muestran diferencias que se explican abajo.`}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                <Metrica etiqueta="Chequeos aprobados" valor={`${entero(ok)} de ${entero(total)}`} />
                <Metrica etiqueta="Chequeos con diferencias" valor={entero(fallidos.length)} detalle={sinDiferencias ? "Nada que revisar" : "Revisar el detalle"} />
              </div>
              {fallidos.length > 0 ? (
                <div className="mt-4">
                  <TablaScroll etiqueta="Chequeos con diferencias">
                    <table className="w-full">
                      <caption className="sr-only">Chequeos de auditoría con diferencias</caption>
                      <thead>
                        <tr><th className={TH}>Chequeo</th><th className={TH}>Esperado</th><th className={TH}>Obtenido</th><th className={TH}>Explicación</th></tr>
                      </thead>
                      <tbody>
                        {fallidos.map((c) => (
                          <tr key={c.chequeo} className={FILA}>
                            <td className={TD}>{c.chequeo}</td>
                            <td className={TD}>{c.valor_esperado ?? "—"}</td>
                            <td className={TD}>{c.valor_obtenido ?? "—"}</td>
                            <td className={TD}>{c.explicacion ?? <span className="text-[var(--portal-subtle)]">sin explicación registrada</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </TablaScroll>
                </div>
              ) : null}
            </section>

            <section className={CARD} aria-label="Límites de los datos">
              <Titulo sub="Qué cubren los datos y qué no, para no pedirles más de lo que pueden dar.">Cobertura y límites de los datos</Titulo>
              <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-[var(--portal-muted)]">
                {d.cobertura.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </section>

            <details className="rounded-md border border-[var(--boveda-linea)] p-4">
              <summary className="cursor-pointer text-base font-semibold text-[var(--portal-fg)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--ucn-azul-claro)]">
                Detalle técnico
                <span className="ml-2 text-xs font-normal text-[var(--portal-muted)]">cargas por fuente y tablas de resultados</span>
              </summary>
              <div className="mt-4 space-y-5">
                <section aria-label="Últimas cargas por fuente">
                  <Titulo sub="Última carga registrada de cada fuente de datos.">Cargas por fuente</Titulo>
                  {d.cargas.length === 0 ? <Vacio>No hay cargas registradas.</Vacio> : (
                    <TablaScroll etiqueta="Cargas por fuente">
                      <table className="w-full">
                        <caption className="sr-only">Última carga por fuente</caption>
                        <thead>
                          <tr><th className={TH}>Fuente</th><th className={TH}>Estado</th><th className={TH}>Terminó de cargar</th><th className={TH}>Filas de origen</th><th className={TH}>Filas cargadas</th></tr>
                        </thead>
                        <tbody>
                          {d.cargas.map((c) => (
                            <tr key={c.fuente} className={FILA}>
                              <td className={TD}>{c.fuente}</td>
                              <td className={TD}><Insignia tono={c.estado.toLowerCase().startsWith("ok") || c.estado.toLowerCase() === "completado" ? "azul" : "aviso"}>{c.estado}</Insignia></td>
                              <td className={TD}>{fechaHora(c.terminado_en ?? c.carga_wh)}</td>
                              <td className={TD}>{entero(c.filas_origen)}</td>
                              <td className={TD}>{entero(c.filas_insertadas)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </TablaScroll>
                  )}
                </section>

                <section aria-label="Tablas de resultados">
                  <Titulo sub="Tablas resumen (marts) que alimentan las demás pestañas.">Tablas de resultados</Titulo>
                  {d.marts.length === 0 ? <Vacio>Las tablas de resultados aún no están construidas.</Vacio> : (
                    <TablaScroll etiqueta="Tablas de resultados">
                      <table className="w-full">
                        <caption className="sr-only">Estado de construcción de cada tabla de resultados</caption>
                        <thead>
                          <tr><th className={TH}>Tabla</th><th className={TH}>Filas</th><th className={TH}>Construida</th><th className={TH}>Último período</th></tr>
                        </thead>
                        <tbody>
                          {d.marts.map((m) => (
                            <tr key={m.mart} className={FILA}>
                              <td className={TD}>{m.mart}</td>
                              <td className={TD}>{entero(m.filas)}</td>
                              <td className={TD}>{fechaHora(m.construido_en)}</td>
                              <td className={TD}>{m.periodo_maximo ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </TablaScroll>
                  )}
                </section>
              </div>
            </details>
          </div>
        );
      }}
    </Carga>
  );
}
