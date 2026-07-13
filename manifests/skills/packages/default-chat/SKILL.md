---
name: Default Chat
description: Skill base para el agente de chat por defecto. No expone tools propios.
version: 1.0.0
---

# Default Chat Skill

Skill de gobernanza para el agente `default_chat`. No contiene herramientas propias;
existe para que el Policy Gate pueda autorizar turnos del agente mediante una regla
`allow` catch-all.
