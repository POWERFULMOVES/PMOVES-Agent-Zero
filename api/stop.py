from agent import AgentContext
from helpers.api import ApiHandler, Request, Response


def stop_context(context: AgentContext) -> dict:
    was_running = context.is_running()

    context.kill_process()
    context.paused = False
    context.log.set_progress("", active=False)

    message = "Agent process stopped."
    context.log.log(type="info", content=message, finished=True)

    return {
        "message": message,
        "context": context.id,
        "stopped": was_running,
    }


class Stop(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", "")
        if not isinstance(ctxid, str) or not ctxid.strip():
            return Response(
                '{"error": "context is required"}',
                status=400,
                mimetype="application/json",
            )

        context = AgentContext.use(ctxid.strip())
        if not context:
            return Response(
                '{"error": "Chat context not found"}',
                status=404,
                mimetype="application/json",
            )
        return stop_context(context)
