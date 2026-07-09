import { WarnIcon } from "./icons";

/**
 * Banner permanente de IA (tarea 5.5, d10-design-system-shell).
 * `.ai-banner` (styles/tokens.css §5.25, portado verbatim en la tarea 3.3):
 * presente en TODA vista autenticada, para todos los roles, SIN ningún
 * control de cierre (escenario "Banner presente sin acción de cierre").
 *
 * Las dos variantes de texto (`.ai-banner__text--full`/`--short`, ambas del
 * catálogo i18n) viven SIEMPRE en el DOM; `styles/shell.css` alterna cuál
 * se ve por `@media`. Así el banner "se acorta en móvil sin desaparecer"
 * (nunca deja de estar presente, solo cambia el texto) y el test de jsdom
 * puede verificar ambos textos sin depender de que el motor de CSS evalúe
 * media queries (jsdom no lo hace).
 */

export type AiBannerProps = {
  /** design/VISTAS/01-acceso-shell.md Vista 3: texto completo (desktop/tablet). */
  textFull: string;
  /** Vista 3, sección Móvil: texto acortado (<768 px). */
  textShort: string;
};

export function AiBanner({ textFull, textShort }: AiBannerProps) {
  return (
    <div className="ai-banner">
      <WarnIcon />
      <span className="ai-banner__text--full">{textFull}</span>
      <span className="ai-banner__text--short">{textShort}</span>
    </div>
  );
}
