"""plnt-cloud workflow + activity modules.

Intentionally bare — do NOT re-export from `workflows.activities` here.
That module transitively imports httpx (via microagents.agent_loop), and
the Temporal sandbox validator walks the package init when loading any
sibling workflow module. Re-exporting activities means loading
ConversationWorkflow under the sandbox eagerly tries to import httpx,
which is restricted unless the caller has configured the passthrough
list (workflows/worker.py does; ad-hoc Worker(...) construction in
tests does not).

Import workflows and activities explicitly from their submodules:
    from workflows.session import ConversationWorkflow
    from workflows.activities import run_microagent, notify_booking
"""
