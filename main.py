import asyncio
import os
from dotenv import load_dotenv
import parlant.sdk as p
from parlant_context.parlant_tools import validate_a2a_ocl_expression

# Carichiamo automaticamente le variabili d'ambiente dal file .env
load_dotenv()

async def main():
    # Siccome usi OpenAI, specifichiamo esplicitamente ad p.Server() di usare OpenAI
    async with p.Server(nlp_service=p.NLPServices.openai) as server:
        # 1. Creazione dell'Agente SwarmDev Orchestrator
        agent = await server.create_agent(
            name="SwarmDev Orchestrator",
            description="Sei l'orchestratore del sistema multi-agente SwarmDev, responsabile dello sviluppo software parallelo basato su contratti rigorosi e validazioni A2A-OCL."
        )
        
        # 2. Configurazione del Glossary (Vocabolario di Settore)
        await agent.create_term(
            name="A2A-OCL",
            description="Agent-to-Agent Object Constraint Language. È il linguaggio utilizzato in SwarmDev per definire i contratti e le specifiche architetturali tra agenti. Deve rispettare una precisa grammatica EBNF.",
            synonyms=["OCL", "Object Constraint Language", "Vincoli OCL"]
        )
        
        await agent.create_term(
            name="Contratto JSON",
            description="L'artefatto finale che un agente produce al termine del suo lavoro. Il contratto definisce rigidamente interfacce, modelli e vincoli A2A-OCL.",
            synonyms=["Contract", "JSON Contract", "Schema Architetturale"]
        )
        
        await agent.create_term(
            name="Micro-Loop",
            description="Il ciclo di validazione immediato dove l'agente verifica iterativamente le proprie espressioni A2A-OCL o i propri contratti JSON fino a che non risultano totalmente corretti e validi.",
            synonyms=["Micro Loop", "Self-Validation Loop", "Ciclo di Validazione"]
        )

        # 3. Configurazione delle Guidelines e del Tool
        await agent.create_guideline(
            condition="prima di inserire o confermare un'espressione A2A-OCL all'interno di un Contratto JSON",
            action="Valida sempre e rigorosamente la sintassi dell'espressione utilizzando il tool 'validate_a2a_ocl_expression' disponibile. Correggi l'espressione iterativamente e ripeti il tool (Micro-Loop) in caso di errori fino ad ottenere 'success'!",
            tools=[validate_a2a_ocl_expression]
        )
        
        print("✅ SwarmDev Orchestrator inizializzato.")
        print("Agent, Termini Glossary e Guideline caricati con successo.")
        print("Server in esecuzione (http://localhost:8800)...")


if __name__ == "__main__":
    asyncio.run(main())
