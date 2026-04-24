import asyncio
import os
from parlant import sdk as p

# Debug: verifica che le variabili d’ambiente siano caricate
print("MODEL:", os.getenv("OPENAI_MODEL"))
print("EMBED:", os.getenv("OPENAI_EMBEDDING_MODEL"))

# ---------------------------------------------------------
#  MAIN
# ---------------------------------------------------------

async def main():

    # Avvio del server Parlant
    async with p.Server(
        nlp_service="openai",   # <-- CORRETTO per Parlant 3.3.1
        log_level=p.LogLevel.DEBUG
    ) as server:

        print("🚀 Avvio del Server Integrato SwarmDev...")

        # -------------------------------------------------
        # 1. Creazione dell’agente
        # -------------------------------------------------
        agent = await server.create_agent(
            name="SwarmDev Orchestrator",
            instructions="Sei l’orchestratore del sistema SwarmDev. Coordina tool e agenti.",
        )
        print("🧠 Agente creato:", agent.id)

        # -------------------------------------------------
        # 2. Registrazione del tool Python
        # -------------------------------------------------
        @server.tool()
        async def echo_tool(text: str) -> str:
            """Semplice tool di test."""
            return f"Echo: {text}"

        print("🔧 Tool registrato: echo_tool")

        # -------------------------------------------------
        # 3. Creazione della guideline
        # -------------------------------------------------
        guideline = await server.create_guideline(
            name="SwarmDev Guideline",
            content="Regole operative per l’orchestratore SwarmDev."
        )
        print("📜 Guideline creata:", guideline.id)

        # -------------------------------------------------
        # 4. Associazione guideline → agente
        # -------------------------------------------------
        await server.assign_guideline(agent.id, guideline.id)
        print("🔗 Guideline assegnata all’agente.")

        # -------------------------------------------------
        # 5. Test: invio messaggio all’agente
        # -------------------------------------------------
        response = await server.send_message(
            agent_id=agent.id,
            message="Ciao agente, esegui il tool echo con il testo 'test'."
        )

        print("💬 Risposta agente:")
        print(response)

# ---------------------------------------------------------
#  ENTRYPOINT
# ---------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())

