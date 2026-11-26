# web/backend

Web backend handlers for mesh, voice, chat demo and security.

Read [repository instructions](../../AGENTS.md) and [codebase navigation](../../CODEBASE.md). See the [implementation guide](../../docs/codebase/IMPLEMENTATION.md) and [complete baseline file inventory](../../docs/codebase/FILE_INDEX.md). This is a navigation note, not proof that a feature is enabled or deployed.

| Local file | Navigation | Evidence |
| --- | --- | --- |
| [`__init__.py`](__init__.py) | Navigation hint:   init  ; source behavior not independently reviewed. | Indexed |
| [`chat_demo.py`](chat_demo.py) | Password-gated multimodal Chat Lab: session, request limits, attachment processing and central inference calls. | Reviewed |
| [`mesh.py`](mesh.py) | Personal-only model catalog/chat, attachment parsing and gated image/audio/video operations; per-process quotas are not financial controls. | Reviewed |
| [`security.py`](security.py) | Shared same-origin, CSRF and Personal session checks for compatibility Mesh and realtime voice. | Reviewed |
| [`voice.py`](voice.py) | Compatibility WebRTC SDP exchange using server-side Personal authorization and CSRF checks. | Reviewed |
