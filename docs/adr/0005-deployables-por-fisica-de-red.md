# ADR-0005 — Deployables separados solo por física de red

- **Estado:** aceptado (2026-07-09)

## Contexto

Decidido el monolito modular ([ADR-0001](0001-monolito-modular-hexagonal.md)), quedaba definir cuántos deployables existen. El blueprint v2.4 impone dos restricciones físicas: (a) el ERP de cada cliente vive en su propio servidor Windows con red privada, y los agentes tienen prohibido el acceso directo a la base (patrón 11: ERP Safe Query API); (b) mientras no existan credenciales de servicio por cliente, la conectividad aprovecha la VPN activa en la máquina del usuario (patrón 10: Local Edge Connector).

## Decisión

Exactamente **tres deployables**, cada uno justificado por dónde tiene que correr:

| Deployable | Dónde corre | Restricción física que lo separa |
|---|---|---|
| Plataforma core | Servidor de Resultar / nube | Ninguna — es el monolito modular |
| ERP Safe Query API | Junto al Protheus de cada cliente | Debe alcanzar DBAccess/SQL en la red del cliente; allowlist y credenciales por cliente |
| Edge Connector Windows | Máquina del usuario | Debe usar la VPN activa de esa máquina |

**Regla para el futuro:** extraer un cuarto deployable requiere un ADR nuevo que demuestre una restricción física u operativa real (red, seguridad, ciclo de release incompatible). "Quedaría más limpio" no es una restricción.

## Alternativas consideradas

1. **Todo en un solo deployable** — imposible: la plataforma core no puede alcanzar la red privada de cada cliente ni la VPN del usuario.
2. **Microservicios por bounded context** — rechazada (ver ADR-0001).
3. **ERP Safe Query API como módulo del core con túnel de red** — rechazada: la superficie de seguridad del ERP debe estar bajo control del cliente, con su propio allowlist, versionado y kill switch, sin exponer la red del cliente al SaaS.

## Consecuencias

- (+) Cada superficie de seguridad tiene su dueño: el core gobierna, la Safe Query API filtra en origen, el Edge Connector limita en el borde.
- (+) Los satélites son pequeños y aburridos (FastAPI + allowlist; cliente Windows + tool allowlist local): mantenibles por un junior.
- (−) Tres pipelines de release → mitigado: los satélites cambian poco una vez estables.
- (−) Versionado de contratos entre core y satélites → mitigado: OpenAPI 3.1 versionado como contrato explícito.

## Fuentes

- Blueprint v2.4, Patrón 10 (Local Edge Connector con VPN del usuario) y Patrón 11 (ERP Safe Query API + MCP Server) — [referencia local](../referencias/arquitectura_plataformas_ia_internas_v2_4_agentic_scaffolding.md)
- Contexto operativo Resultar: servidores dedicados por cliente, Windows Server, DBAccess obligatorio — [referencia local](../referencias/contexto-resultar-soluciones.md)
