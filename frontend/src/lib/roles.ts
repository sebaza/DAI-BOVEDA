import type { AuthUser, BovedaRole } from "./session";

export const ETIQUETA_ROL: Record<string, string> = {
  admin: "Administración",
  equipo: "Equipo DAI",
  lector: "Solo lectura",
};

export function etiquetaRol(rol: BovedaRole | string | null | undefined): string {
  return rol ? ETIQUETA_ROL[rol] ?? rol : "";
}

/** El administrador es global: se rotula como tal, sea cual sea su rol en cada módulo. */
export function rolDelUsuario(usuario: AuthUser): string {
  return etiquetaRol(usuario.is_admin ? "admin" : usuario.role);
}
