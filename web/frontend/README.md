# DragonZpyder React frontend

The UI is built using React 19, Vite 7 and Node.js 22 for the build pipeline.
Python FastAPI still serves the production HTTP API and compiled files.
Do **not** put model keys or session secrets into Vite public environment values.

- `npm install && npm run build` builds `web/dist/`.
- `npm run dev` uses the Vite development server; run FastAPI locally on port 8080 for API proxying.
- `npm run test` validates the built entry points and key account/chat element IDs.

## Design and migration strategy

The legacy `web/{index,app,account}.html` files are canonical layout templates
for now. The Vite multi-page build preserves their original metadata and
server-visible body markup. React **hydrates** them and provides the new
home runtime/status components.

The existing app, account, AI Mesh and companion JavaScript modules are
transitional *adapters* loaded after hydration, not duplicated business logic.
Move each feature to idiomatic React components/hooks behind API contracts
one at a time. Avoid React state updates that rerender nodes which those
temporary adapters mutate. Do not change the existing CSS palette/IDs
without updating contract tests.

API, auth, CSRF, model spending controls and Operly workspace permissions
remain enforced server-side by FastAPI and the authorised backend.
