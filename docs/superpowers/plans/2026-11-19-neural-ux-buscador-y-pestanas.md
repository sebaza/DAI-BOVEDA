# DAI Neural UX: program search and tab reorganization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A searchable population selector shared by four tabs, regrouped and renamed tabs, the population visible on every block, and the high-priority UX fixes from the 19-11-2026 audit.

**Architecture:** Frontend only (`frontend/src`). `NeuralSelectorPoblacion` gains an accessible combobox. `NeuralPanel` owns the shared selection and the tab groups. Blocks read the active population from a context.

**Tech Stack:** Next.js / React / TypeScript, Tailwind, ECharts (CDN-loaded). There is no frontend test runner. Every task's check is `cd frontend && npx tsc --noEmit`, plus a controller browser check at the end.

**Spec:** `docs/superpowers/specs/2026-11-19-neural-ux-buscador-y-pestanas-design.md`. Evidence: `docs/superpowers/specs/2026-11-19-neural-ux-auditoria.md` (A1–A8).

## Global Constraints
- Frontend only, with no API changes. No per-student lists, names, RUT or teacher rankings.
- Neutral Spanish copy. No horizontal overflow at 375 px. New controls have touch targets of at least 44 px.
- T1–T6 codes only next to their Spanish name.
- Keep the acceptance gate, the single `POCOS_CASOS` threshold, and the `resolverFiltro` rule (never request a program the tab does not list).
- Preserve each file's existing line endings (LF or CRLF; compare against the task's snapshot).
- No commits, no servers in subagents, no subagents spawned by subagents.

## Review Focus
1. Search with accents or partial codes («ingenieria», «8616», «comp»): the user expects matches across all faculties.
2. Choosing a program that the active tab does not list: the user expects the existing note, not an empty or broken tab.
3. Keyboard-only use of the combobox (arrows, Enter, Escape, Tab): the user expects it to work like a native select.
4. The tab bar at 375 px after the renames: every tab must be reachable and visibly scrollable.
5. A chart whose CDN script fails: the user expects a visible message, not an endless skeleton.

---

### Task 1: Searchable shared population selector
**Files:** `frontend/src/components/NeuralSelectorPoblacion.tsx`, `frontend/src/lib/neuralLenguaSimple.ts` (SELECTOR_TEXTOS).
- Add a combobox «Buscar facultad o programa» (ARIA 1.2 combobox + listbox) above the existing faculty → program lists, and keep those lists.
- Matching:
  - Starts at 2 characters.
  - Case- and accent-insensitive (`normalize("NFD")`, strip U+0300–U+036F).
  - Matches the program name, the program code or the faculty name, across the whole `jerarquia`.
- Each option shows «Nombre (código)», with the faculty on a second line. Faculties appear as options too.
- Choosing an option sets `{facultad, programa, nombrePrograma}` in one `onSeleccion` call.
- Live region with the result count. Keyboard behaviour: ↑ ↓ move, Enter chooses, Escape closes, Tab leaves.
- The program `<option>`s in the existing list also show «Nombre (código)».
- `resolverFiltro` stays unchanged.
- Check: `npx tsc --noEmit` clean.

### Task 2: Tab groups, renames, mobile tab bar, shared selector in Cohortes and «Modelo por facultad»
**Files:** `NeuralPanel.tsx`, `NeuralUI.tsx` (Pestanas), `NeuralFacultades.tsx`, `NeuralCohortes.tsx`, `NeuralModelos.tsx` (link label), `neuralLenguaSimple.ts` (PROPOSITO_PESTANA, link texts).
- New order and groups:
  - «Lo que pasó»: Histórico, Cohortes, Traslados.
  - «Lo que viene»: Proyecciones.
  - «Cuánto confiar»: Modelos, «Modelo por facultad», «Calidad de los datos».
- Show the groups with visual separators, and give the group names to assistive tech.
- Histórico stays the default. Ids stay the same, so state keeps working.
- Mobile tab bar: edge fade plus `scrollIntoView` of the active tab, reusing the `pestanas-fade-*` and `pestanas-scroll` classes from `PercepcionPanel.tsx`. Internal jumps (`onVerFacultades`, `onVerTraslados`) also scroll the bar.
- «Modelo por facultad»:
  - Receives `seleccion` as its initial value: a faculty, or a program at program level.
  - Offers Toda la UCN if its data has a UCN row. If it doesn't, says so.
  - Its purpose text states that it measures the model, not the history, and points to Histórico.
- Cohortes:
  - Uses `NeuralSelectorPoblacion` (with search) over its own program list, built from `/neural/programas` grouped by faculty.
  - Shares the selection with the panel.
  - Keeps its «elige un programa» state when no program is chosen.
- Check: `tsc` clean.

### Task 3: Population visible on every block, and on tabs without a filter
**Files:** `NeuralLoQuePasoTemas.tsx` (Bloque), `NeuralLoQuePaso.tsx`, `NeuralLoQueViene.tsx`, `NeuralModeloEtiqueta.tsx` (PoblacionContext), tab components without a filter.
- `Bloque` renders a compact population chip in its header from `PoblacionContext`, for example «Escuela de Ingeniería · Ingeniería Civil Industrial (8616)» or «Toda la UCN».
- Blocks with `aplica_a_poblacion: false` show «Toda la UCN».
- Modelos, Calidad de los datos and Traslados show one line at the top: «Esta sección no cambia con la población elegida». Reuse the existing text in `neuralLenguaSimple.ts`.
- Check: `tsc` clean.

### Task 4: Reading order and honest copy
**Files:** `NeuralLoQuePaso.tsx`, `NeuralLoQuePasoTemas.tsx`, `NeuralLoQueViene.tsx`, `neuralLenguaSimple.ts`.
- On mobile, `Clave` comes before the chart (`order-first lg:order-none`, or the equivalent) in every block that pairs a chart with a `Clave`.
- Permanencia: the «¿Cuántos pasaron al año siguiente?» block comes first. Renumber the blocks.
- Histórico opens with a «Lo esencial» strip of 3 figures from the Histórico response, each with its n, its «pocos casos» mark when it applies, and a link that scrolls to its block. The default choice: continuity at the next year, dropouts in year 1, and eliminated students in the last full year.
- Truncated lists (`NeuralLoQuePasoTemas.tsx:197, 238, 282, 427`):
  - The copy says «se muestran los N mayores de M».
  - A collapsed table lists all of them.
  - Fix the «se listan todos» promises (`neuralLenguaSimple.ts:529, 544`).
- Check: `tsc` clean.

### Task 5: Chart trust
**Files:** `EChartsChart.tsx`, `NeuralUI.tsx` (MarcoGrafico, LeyendaPocosCasos), `NeuralCohortes.tsx`, Histórico chart callers, `neuralGraficos*.ts` (tooltips).
- `EChartsChart`: on load error, or after a timeout of about 8 s, replace the skeleton with «No se pudo cargar el gráfico» and point to the data table when one exists.
- `MarcoGrafico`: an optional `datos: {columnas, filas}` prop renders a collapsed «Ver los datos» table. Wire it into the Histórico charts that have no equivalent table: semesters, entry profile, first semester, expected, time to graduation, signals.
- The Cohortes curve uses `MarcoGrafico`.
- «Pocos casos» in charts: besides the lighter colour, the tooltip says «pocos casos (n = X)», and the legend item says so in text.
- Check: `tsc` clean.

### Task 6: Verification and docs (controller)
- Browser check at desktop size and at 375 px:
  - Search for «ingenieria», «8616» and «comp».
  - Pick a program that is missing in Proyecciones, then use the keyboard only.
  - Check each tab group, the chips, «Lo esencial», «Ver los datos» and the console.
- Set the spec state to «construido». Run the full hygiene grep from the previous plan.
