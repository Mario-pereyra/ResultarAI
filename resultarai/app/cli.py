"""CLI de validacion de manifiestos (`resultarai-validate`, a02-core-manifiestos tarea 4.1).

Transporte para `load_registries` (`core/registries/loader.py`): "un solo camino de
validacion, tres disparadores" (desarrollador local, CI, arranque de la plataforma). Este
modulo es el disparador de linea de comandos -- parsea argv, resuelve `manifests_dir`,
llama a `load_registries` sin duplicar su logica, e imprime un resultado claro por
manifest o el error con archivo y causa. No arranca la plataforma, no importa adapters
(LiteLLM, MCP, LangGraph, Postgres) y no toca red: solo lee YAML y aplica schemas, igual
que `load_registries`.

**Decision -- no existe una `validate_manifests` nueva en `core/`.** `load_registries`
(`manifests_dir: Path) -> Registries`) ya ES la funcion unica de validacion: por
manifest, parsea YAML y valida contra su schema Pydantic (`ManifestLoadError` si falla,
citando archivo y causa; `DuplicateManifestIdError` ante un `id` repetido dentro del
mismo tipo) y despues valida las referencias cruzadas del conjunto completo
(`DanglingReferenceError`) antes de devolver los 6 Registries -- ver el docstring de
`loader.py`, que explica por que esta integrada ahi y no en una funcion separada que
alguien pudiera olvidar llamar. Envolverla en otra funcion de `core/` con el mismo
contrato (`validate_manifests(manifests_dir) -> Registries`) no anadiria nada: misma
firma, mismos errores, una capa de indireccion mas que mantener sincronizada. Por eso
este CLI importa `load_registries` directamente; el arranque fail-fast de la plataforma
(`app/` futuro, requirement "Validacion de manifiestos al arranque") hara lo mismo.

**Decision -- default de `--manifests-dir`.** Por defecto se resuelve contra el
directorio de trabajo actual (`Path.cwd() / "manifests"`), no contra la ubicacion de
este archivo ni una ruta absoluta harcodeada: es el comportamiento esperado de un CLI
que un desarrollador invoca con `uv run resultarai-validate` desde la raiz del repo, y el
mismo que usara el job de CI (que hace `cd` a la raiz del repo antes de invocarlo).
`core/` nunca resuelve esta ruta (regla dura 1); quien necesite apuntar a otro
`manifests/` (p. ej. un test con `tmp_path`) lo hace explicito con `--manifests-dir`.

**Decision -- `--manifests-dir` ausente es un error del CLI, no de `core/`.**
`load_registries` trata cada subdirectorio ausente (`agents/`, `skills/`, ...) como
vacio -- valido a proposito, porque un `manifests/` parcial en un test unitario no debe
fallar solo por eso (ver `loader.py`). Pero que el propio `--manifests-dir` no exista
casi siempre es un error de invocacion (ruta mal escrita, cwd equivocado): reportarlo
como "0 manifiestos, exit 0" seria un falso verde silencioso. Por eso el CLI valida la
existencia de `--manifests-dir` antes de llamar a `load_registries` y falla con exit
distinto de 0 si no existe, en vez de delegarle esa comprobacion a `core/`.

**Decision -- `main()` devuelve el exit code, no llama a `sys.exit`.** El entry point de
`[project.scripts]` (`resultarai-validate = "resultarai.app.cli:main"`) hace
`sys.exit(main())` en el wrapper que genera `uv`/`pip`; `main()` en si misma solo
devuelve `int` para que los tests puedan invocarlo con un `argv` controlado y comprobar
el codigo devuelto sin tener que capturar `SystemExit`.

Solo stdlib (`argparse`): regla dura del proyecto, sin click ni typer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from resultarai.core.registries import (
    DanglingReferenceError,
    DuplicateManifestIdError,
    ManifestLoadError,
    Registries,
    load_registries,
)

__all__ = ["main"]

# Orden de reporte: el mismo en el que `load_registries` construye los Registries.
_REGISTRY_LABELS: tuple[tuple[str, str], ...] = (
    ("agents", "Agents"),
    ("skills", "Skills"),
    ("tools", "Tools"),
    ("policies", "Policies"),
    ("routing", "Routing"),
    ("evals", "Eval Templates"),
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resultarai-validate",
        description=(
            "Valida todos los manifiestos YAML de un directorio manifests/ contra sus "
            "schemas Pydantic y sus referencias cruzadas. No arranca la plataforma, no "
            "importa adapters y no accede a red: solo lee YAML y aplica schemas."
        ),
    )
    parser.add_argument(
        "--manifests-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Directorio manifests/ a validar (default: ./manifests relativo al "
            "directorio de trabajo actual)."
        ),
    )
    return parser


def _format_report(registries: Registries, manifests_dir: Path) -> str:
    """Resultado claro por manifest: cuantos y cuales, por cada uno de los 6 Registries."""
    lines = [f"Validando manifiestos en {manifests_dir}"]
    total = 0
    for attr, label in _REGISTRY_LABELS:
        registry = getattr(registries, attr)
        ids = sorted(manifest.id for manifest in registry)
        total += len(ids)
        joined = ", ".join(ids) if ids else "(ninguno)"
        lines.append(f"  OK  {label} ({len(ids)}): {joined}")
    lines.append(f"OK: {total} manifiestos validos, referencias cruzadas resueltas.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de `resultarai-validate`. Devuelve el exit code (0 = todo valido)."""
    args = _build_parser().parse_args(argv)
    manifests_dir: Path = (
        args.manifests_dir if args.manifests_dir is not None else Path.cwd() / "manifests"
    )

    if not manifests_dir.is_dir():
        print(
            f"ERROR: {manifests_dir} no existe o no es un directorio "
            "(revisa --manifests-dir, o el directorio de trabajo desde el que invocas "
            "el CLI si usas el default).",
            file=sys.stderr,
        )
        return 2

    try:
        registries = load_registries(manifests_dir)
    except (ManifestLoadError, DuplicateManifestIdError, DanglingReferenceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(_format_report(registries, manifests_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
